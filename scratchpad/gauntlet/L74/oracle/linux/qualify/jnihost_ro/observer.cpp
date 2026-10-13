#include <jni.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdint>
#include <cstdio>
#include "private_binding.h"

#ifndef ORACLE_READ_ONLY
#error Read-only build required
#endif

static void fail(JNIEnv* env, const char* message) {
    jclass cls = env->FindClass("java/lang/IllegalStateException");
    if (cls) env->ThrowNew(cls, message);
}

extern "C" JNIEXPORT jstring JNICALL
Java_royale_nativehost_JniHost_nativeRead(JNIEnv* env, jclass, jstring path) {
    const char* chars = env->GetStringUTFChars(path, nullptr);
    if (!chars) return nullptr;
    // Never load libg here, never call JNI_OnLoad ourselves.
    void* handle = dlopen(chars, RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD);
    env->ReleaseStringUTFChars(path, chars);
    if (!handle) { fail(env, "HOST_LIBG_NOT_LOADED"); return nullptr; }
    void* symbol = dlsym(handle, "JNI_OnLoad");
    Dl_info info{};
    if (!symbol || !dladdr(symbol, &info) || !info.dli_fbase) {
        dlclose(handle); fail(env, "HOST_SYMBOL_UNAVAILABLE"); return nullptr;
    }
    uintptr_t base = reinterpret_cast<uintptr_t>(info.dli_fbase);
    uintptr_t delta = reinterpret_cast<uintptr_t>(symbol) - base;
    if (delta != EXPECTED_JNI_DELTA) {
        dlclose(handle); fail(env, "HOST_JNI_IDENTITY_MISMATCH"); return nullptr;
    }
    // Kernel-mediated reads return failure for unmapped memory. No dereference
    // of a candidate pointer, no pointer chasing past the identifying vtable.
    int fd = open("/proc/self/mem", O_RDONLY | O_CLOEXEC);
    uint64_t game = 0, vtable = 0;
    bool readable = fd >= 0 && pread(fd, &game, sizeof(game),
        static_cast<off_t>(base + GAME_MAIN_GLOBAL)) == sizeof(game);
    bool identified = readable && game != 0 &&
        pread(fd, &vtable, sizeof(vtable), static_cast<off_t>(game)) == sizeof(vtable) &&
        vtable == base + GAME_MAIN_VTABLE;
    if (fd >= 0) close(fd);
    const char* status = !readable ? "unreadable" : game == 0 ? "absent" :
        identified ? "identified" : "unverified_pointer";
    char pointer[40];
    if (identified) std::snprintf(pointer, sizeof(pointer), "\"%llu\"", static_cast<unsigned long long>(game));
    else std::snprintf(pointer, sizeof(pointer), "null");
    char payload[512];
    std::snprintf(payload, sizeof(payload),
        "{\"module_base\":\"%llu\",\"jni_delta\":\"%llu\",\"game_main\":%s,"
        "\"game_main_status\":\"%s\",\"atomic\":false}",
        static_cast<unsigned long long>(base), static_cast<unsigned long long>(delta), pointer, status);
    dlclose(handle);
    return env->NewStringUTF(payload);
}
