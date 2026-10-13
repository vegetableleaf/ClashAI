#include <jni.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include "binding_keys.h"

#ifndef ORACLE_NO_PATCHES
#error No-patches build required
#endif

// All writes below are to observer-owned storage. There is no target write API.
struct Module {
    void* handle = nullptr;
    uintptr_t base = 0;
    jlong b[B_COUNT]{};
    int fd = -1;
    Module(JNIEnv* env, jstring path, jlongArray values) {
        if (env->GetArrayLength(values) != B_COUNT) throw std::runtime_error("HOST_BINDING_COUNT");
        env->GetLongArrayRegion(values, 0, B_COUNT, b);
        if (env->ExceptionCheck()) throw std::runtime_error("HOST_BINDING_READ");
        for (jlong v : b) if (v < 0 || static_cast<uint64_t>(v) >= (uint64_t(1) << 32))
            throw std::runtime_error("HOST_BINDING_RANGE");
        const char* chars = env->GetStringUTFChars(path, nullptr);
        if (!chars) throw std::runtime_error("HOST_PATH");
        handle = dlopen(chars, RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD);
        env->ReleaseStringUTFChars(path, chars);
        if (!handle) throw std::runtime_error("HOST_LIBG_NOT_LOADED");
        void* symbol = dlsym(handle, "JNI_OnLoad");
        Dl_info info{};
        if (!symbol || !dladdr(symbol, &info) || !info.dli_fbase ||
            reinterpret_cast<uintptr_t>(symbol) - reinterpret_cast<uintptr_t>(info.dli_fbase) !=
                static_cast<uintptr_t>(b[B_JNI_ON_LOAD])) {
            dlclose(handle); handle = nullptr;
            throw std::runtime_error("HOST_JNI_IDENTITY_MISMATCH");
        }
        base = reinterpret_cast<uintptr_t>(info.dli_fbase);
        fd = open("/proc/self/mem", O_RDONLY | O_CLOEXEC);
        if (fd < 0) {
            dlclose(handle); handle = nullptr;
            throw std::runtime_error("HOST_MEMORY_UNAVAILABLE");
        }
    }
    ~Module() { if (fd >= 0) close(fd); if (handle) dlclose(handle); }
    template<class T> bool read(uintptr_t p, T& out) {
        return p && p < (uint64_t(1) << 63) &&
            pread(fd, &out, sizeof(out), static_cast<off_t>(p)) == sizeof(out);
    }
    uintptr_t pointer(uintptr_t p) { uintptr_t v = 0; read(p, v); return v; }
    uintptr_t global(BindingKey key) { return pointer(base + b[key]); }
    bool identified(uintptr_t p, BindingKey key) {
        return p && pointer(p) == base + b[key];
    }
    bool executable(uintptr_t p) {
        FILE* maps = std::fopen("/proc/self/maps", "r");
        if (!maps) return false;
        char line[1024], perm[5]; unsigned long long lo, hi;
        bool found = false;
        while (std::fgets(line, sizeof(line), maps)) {
            if (std::sscanf(line, "%llx-%llx %4s", &lo, &hi, perm) == 3 &&
                p >= lo && p < hi && perm[0] == 'r' && perm[2] == 'x') { found = true; break; }
        }
        std::fclose(maps); return found;
    }
    template<class F> F function(BindingKey key) {
        uintptr_t p = base + b[key];
        if (!b[key] || !executable(p)) throw std::runtime_error("HOST_FUNCTION_NOT_EXECUTABLE");
        return reinterpret_cast<F>(p);
    }
};

static void fail(JNIEnv* env, const char* message) {
    if (env->ExceptionCheck()) return; // Never replace a libg exception.
    jclass cls = env->FindClass("java/lang/IllegalStateException");
    if (cls) env->ThrowNew(cls, message);
}
static uint64_t now() {
    timespec ts{}; clock_gettime(CLOCK_MONOTONIC, &ts);
    return uint64_t(ts.tv_sec) * 1000000000ULL + ts.tv_nsec;
}
static const char* stages[] = {"load-only", "create_game_main", "game_main_init",
    "data_tables_range", "data_load_tasks", "loading_state", "map_resources",
    "battlefield_cache", "manager_update"};
static int next_stage = 1;
static bool stopped = false;
static uintptr_t saved_tables = 0, location = 0, primary = 0, secondary = 0, cache = 0, battlefield_seen = 0;
static int32_t instance_id = -1;
static void* request = nullptr;

struct Calls {
    JNIEnv* env;
    const char* token;
    int stage;
    void event(const char* name, const char* event_name, uint64_t duration) {
        std::printf("ORACLE_V7_CALL {\"schema_version\":7,\"token\":\"%s\",\"pid\":%d,"
            "\"stage\":\"%s\",\"call\":\"%s\",\"event\":\"%s\","
            "\"monotonic_ns\":\"%llu\",\"elapsed_ns\":\"%llu\"}\n",
            token, int(getpid()), stages[stage], name, event_name,
            static_cast<unsigned long long>(now()), static_cast<unsigned long long>(duration));
        std::fflush(stdout);
    }
    template<class F> auto invoke(const char* name, F f) -> decltype(f()) {
        event(name, "before", 0);
        auto started = now();
        auto value = f();
        if (env->ExceptionCheck()) throw std::runtime_error("NATIVE_JAVA_EXCEPTION_STOP");
        event(name, "after", now() - started);
        return value;
    }
};

struct State {
    uintptr_t game = 0, context = 0, manager = 0, loading = 0, task = 0, tables = 0, resources = 0;
    int32_t phase = -1, task_phase = -1, count = -1;
    uint8_t ready = 0;
    bool game_readable = false, game_ok = false, phase_readable = false, ready_readable = false, tables_saved = false;
    explicit State(Module& m) {
        game_readable = m.read(m.base + m.b[B_GAME_MAIN_GLOBAL_RVA], game);
        game_ok = m.identified(game, B_GAME_MAIN_VTABLE_RVA);
        if (game_ok) context = m.pointer(game + m.b[B_GAME_MAIN_CONTEXT_OFFSET]);
        manager = m.global(B_MANAGER_GLOBAL);
        if (manager) loading = m.pointer(manager + m.b[B_MANAGER_CURRENT_STATE]);
        if (!m.identified(loading, B_LOADING_STATE_VTABLE)) loading = 0;
        if (loading) {
            phase_readable = m.read(loading + m.b[B_LOADING_PHASE], phase);
            task = m.pointer(loading + m.b[B_LOADING_TASK]);
            if (task) {
                tables = m.pointer(task + m.b[B_DATA_TASK_TABLES]);
                resources = m.pointer(task + m.b[B_DATA_TASK_RESOURCES]);
                m.read(task + m.b[B_DATA_TASK_PHASE], task_phase);
            }
        }
        if (!tables && saved_tables) { tables = saved_tables; tables_saved = true; }
        if (tables) ready_readable = m.read(tables + m.b[B_DATA_TABLES_READY], ready);
        if (resources) m.read(resources + m.b[B_RESOURCE_COLLECTION_COUNT], count);
    }
};

extern "C" JNIEXPORT jstring JNICALL
Java_royale_nativehost_AppLibraryLoader_nativeRead(JNIEnv* env, jclass, jstring path, jlongArray binding) {
    try {
        Module m(env, path, binding); State s(m);
        const char* status = !s.game_readable ? "unreadable" : !s.game ? "absent" :
            s.game_ok ? "identified" : "unverified_pointer";
        char game[40], phase[40], ready[8];
        if (s.game_ok) std::snprintf(game, sizeof(game), "\"%llu\"", static_cast<unsigned long long>(s.game));
        else std::snprintf(game, sizeof(game), "null");
        if (s.phase_readable) std::snprintf(phase, sizeof(phase), "%d", s.phase);
        else std::snprintf(phase, sizeof(phase), "null");
        std::snprintf(ready, sizeof(ready), "%s", !s.ready_readable ? "null" : s.ready ? "true" : "false");
        char payload[1400];
        std::snprintf(payload, sizeof(payload),
            "{\"module_base\":\"%llu\",\"jni_delta\":\"%llu\",\"game_main\":%s,"
            "\"game_main_status\":\"%s\",\"context\":\"%llu\",\"manager\":\"%llu\","
            "\"loading_state\":\"%llu\",\"loading_phase\":%s,\"task\":\"%llu\","
            "\"tables\":\"%llu\",\"tables_ready\":%s,\"task_phase\":%d,"
            "\"resource_count\":%d,\"atomic\":false,\"tables_from_saved_receiver\":%s,"
            "\"location\":\"%llu\",\"primary_payload\":\"%llu\",\"secondary_payload\":\"%llu\","
            "\"cache\":\"%llu\",\"battlefield\":\"%llu\",\"instance_id\":%d}",
            static_cast<unsigned long long>(m.base), static_cast<unsigned long long>(m.b[B_JNI_ON_LOAD]),
            game, status, static_cast<unsigned long long>(s.context), static_cast<unsigned long long>(s.manager),
            static_cast<unsigned long long>(s.loading), phase, static_cast<unsigned long long>(s.task),
            static_cast<unsigned long long>(s.tables), ready, s.task_phase, s.count,
            s.tables_saved ? "true" : "false",
            static_cast<unsigned long long>(location), static_cast<unsigned long long>(primary),
            static_cast<unsigned long long>(secondary), static_cast<unsigned long long>(cache),
            static_cast<unsigned long long>(battlefield_seen), instance_id);
        return env->NewStringUTF(payload);
    } catch (const std::exception& e) { fail(env, e.what()); return nullptr; }
}

extern "C" JNIEXPORT jstring JNICALL
Java_royale_nativehost_AppLibraryLoader_nativeStage(JNIEnv* env, jclass caller,
    jstring path, jlongArray binding, jint stage, jstring token_string, jobject assets,
    jstring data, jstring cache_dir, jstring external, jlong available, jint width,
    jint height, jint density, jfloat xdpi, jfloat ydpi, jint graphics_api, jlongArray recipe) {
    const char* token = env->GetStringUTFChars(token_string, nullptr);
    if (!token) return nullptr;
    jstring result = nullptr;
    try {
        if (stopped || stage != next_stage || stage < 1 || stage > 8)
            throw std::runtime_error("HOST_STAGE_ORDER");
        stopped = true; // Cleared only after the entire stage returns successfully.
        Module m(env, path, binding); State s(m); Calls c{env, token, stage};
        using One = void (*)(void*);
        using Predicate = bool (*)(void*);
        using Update = void (*)(void*, float);
        using Getter = void* (*)(void*);
        auto ptr = [](uintptr_t p) { return reinterpret_cast<void*>(p); };
        if (stage == 1) {
            if (s.game || !assets) throw std::runtime_error("HOST_CREATE_PRECONDITION");
            using Create = jstring (*)(JNIEnv*, jclass, jobject, jstring, jstring, jstring,
                jlong, jint, jint, jint, jfloat, jfloat, jint, jstring, jobject);
            auto f = m.function<Create>(B_CREATE_GAME_MAIN);
            result = c.invoke("CreateGameMain", [&] { return f(env, caller, assets, data, cache_dir,
                external, available, width, height, density, xdpi, ydpi, graphics_api, external, nullptr); });
        } else {
            if (!s.game_ok) throw std::runtime_error("HOST_GAME_MAIN_NOT_IDENTIFIED");
            if (stage == 2) {
                if (!s.context) throw std::runtime_error("HOST_GAME_CONTEXT_MISSING");
                using Init = void (*)(void*, void*);
                auto f = m.function<Init>(B_GAME_MAIN_INIT);
                c.invoke("GameMain::init", [&] { f(ptr(s.game), ptr(s.context)); return true; });
            } else if (stage == 3) {
                if (!s.loading || !s.task || !s.tables || !s.resources || s.count <= 0 || s.task_phase != 0)
                    throw std::runtime_error("HOST_DATA_CHAIN_NOT_READY");
                using Range = bool (*)(void*, void*, int32_t, int32_t, int32_t, int32_t, int32_t);
                auto f = m.function<Range>(B_DATA_TABLES_LOAD_RANGE);
                if (!c.invoke("DataTables::loadRange", [&] { return f(ptr(s.tables), ptr(s.resources), 0, 0, 0, 0, s.count); }))
                    throw std::runtime_error("NATIVE_RANGE_INCOMPLETE_STOP");
                saved_tables = s.tables;
            } else if (stage == 4) {
                if (!s.loading || !s.task || s.tables != saved_tables || s.task_phase != 0)
                    throw std::runtime_error("HOST_TASK_CHAIN_CHANGED");
                auto start = m.function<One>(B_DATA_LOAD_TASK_START);
                auto pump = m.function<Predicate>(B_DATA_LOAD_TASK_PUMP);
                auto complete = m.function<Predicate>(B_DATA_LOAD_TASK_COMPLETE);
                c.invoke("DataLoadTask::start", [&] { start(ptr(s.task)); return true; });
                bool done = false;
                for (int i = 0; i < 1024; ++i) {
                    if (c.invoke("DataLoadTask::complete", [&] { return complete(ptr(s.task)); })) { done = true; break; }
                    c.invoke("DataLoadTask::pump", [&] { return pump(ptr(s.task)); });
                    usleep(5000);
                }
                if (!done) throw std::runtime_error("NATIVE_TASK_INCOMPLETE_STOP");
            } else if (stage == 5) {
                if (!s.loading || !s.ready_readable || !s.ready) throw std::runtime_error("HOST_LOADING_NOT_READY");
                auto update = m.function<Update>(B_LOADING_STATE_UPDATE);
                auto complete = m.function<Predicate>(B_LOADING_STATE_COMPLETE);
                bool done = false;
                for (int i = 0; i < 512; ++i) {
                    c.invoke("LoadingState::update", [&] { update(ptr(s.loading), 0.05f); return true; });
                    if (c.invoke("LoadingState::complete", [&] { return complete(ptr(s.loading)); })) { done = true; break; }
                    usleep(5000);
                }
                if (!done) throw std::runtime_error("NATIVE_LOADING_INCOMPLETE_STOP");
            } else if (stage == 6) {
                jsize n = env->GetArrayLength(recipe);
                if (n < 3 || n > 18) throw std::runtime_error("HOST_LOCATION_RECIPE_MISSING");
                jlong chain[18]{}; env->GetLongArrayRegion(recipe, 0, n, chain);
                if (env->ExceptionCheck()) throw std::runtime_error("HOST_LOCATION_RECIPE_READ");
                for (int i = 0; i < n; ++i) if (chain[i] < 0 || uint64_t(chain[i]) >= (uint64_t(1) << 32))
                    throw std::runtime_error("HOST_LOCATION_RECIPE_RANGE");
                location = m.pointer(m.base + chain[0]);
                for (int i = 2; i < n && location; ++i) location = m.pointer(location + chain[i]);
                if (!location || m.pointer(location) != m.base + chain[1])
                    throw std::runtime_error("HOST_LOCATION_NOT_IDENTIFIED");
                auto first = m.function<Getter>(B_LOCATION_FIELD_PRIMARY);
                auto second = m.function<Getter>(B_LOCATION_FIELD_SECONDARY);
                void* a = c.invoke("Location::FileName", [&] { return first(ptr(location)); });
                void* b = c.invoke("Location::TileDataFileName", [&] { return second(ptr(location)); });
                if (!a || !b) throw std::runtime_error("NATIVE_MAP_NAMES_MISSING_STOP");
                auto ctor = m.function<One>(B_RESOURCE_REQUEST_LIST_CONSTRUCTOR);
                using Append = void (*)(void*, void*, int32_t, int32_t, int32_t, int32_t, bool);
                auto append = m.function<Append>(B_RESOURCE_REQUEST_LIST_APPEND);
                auto load = m.function<One>(B_RESOURCE_REQUEST_LIST_LOAD);
                auto resolve = m.function<Getter>(B_DATA_STRING_RESOLVE);
                if (m.b[B_RESOURCE_REQUEST_SIZE] <= 0 || m.b[B_RESOURCE_REQUEST_SIZE] > 4096)
                    throw std::runtime_error("HOST_REQUEST_SIZE");
                request = std::malloc(static_cast<size_t>(m.b[B_RESOURCE_REQUEST_SIZE]));
                if (!request) throw std::runtime_error("HOST_REQUEST_STORAGE");
                // The real constructor initializes the storage; no fake vtable or fields.
                c.invoke("ResourceRequest::constructor", [&] { ctor(request); return true; });
                if (!m.identified(reinterpret_cast<uintptr_t>(request), B_RESOURCE_REQUEST_VTABLE))
                    throw std::runtime_error("HOST_REQUEST_NOT_IDENTIFIED");
                c.invoke("ResourceRequest::append_primary", [&] { append(request, a, -1, -1, -1, -1, false); return true; });
                c.invoke("ResourceRequest::append_secondary", [&] { append(request, b, -1, -1, -1, -1, false); return true; });
                c.invoke("ResourceRequest::load", [&] { load(request); return true; });
                primary = reinterpret_cast<uintptr_t>(c.invoke("resolve_primary", [&] { return resolve(a); }));
                if (!primary) throw std::runtime_error("NATIVE_PRIMARY_MAP_MISSING_STOP");
                secondary = reinterpret_cast<uintptr_t>(c.invoke("resolve_secondary", [&] { return resolve(b); }));
                if (!secondary) throw std::runtime_error("NATIVE_SECONDARY_MAP_MISSING_STOP");
            } else if (stage == 7) {
                if (!request || !primary || !secondary || !location) throw std::runtime_error("HOST_MAP_CHAIN_MISSING");
                auto root = m.function<void* (*)()>(B_BATTLEFIELD_CACHE_ROOT);
                auto id = m.function<int32_t (*)(void*)>(B_DATA_ROW_INSTANCE_ID);
                using Build = void (*)(void*, void*, void*, int32_t);
                auto build = m.function<Build>(B_BUILD_BATTLEFIELD_CACHE);
                auto get = m.function<Getter>(B_LOCATION_BATTLEFIELD);
                cache = reinterpret_cast<uintptr_t>(c.invoke("battlefield_cache_root", [&] { return root(); }));
                if (!cache) throw std::runtime_error("NATIVE_CACHE_ROOT_MISSING_STOP");
                instance_id = c.invoke("DataRow::instanceId", [&] { return id(ptr(location)); });
                if (instance_id < 0) throw std::runtime_error("NATIVE_CACHE_ID_INVALID_STOP");
                c.invoke("build_battlefield_cache", [&] { build(ptr(cache), ptr(primary), ptr(secondary), instance_id); return true; });
                void* battlefield = c.invoke("Location::battlefield", [&] { return get(ptr(location)); });
                battlefield_seen = reinterpret_cast<uintptr_t>(battlefield);
                int32_t count = -1; m.read(cache + m.b[B_BATTLEFIELD_COUNT], count);
                uintptr_t rows = m.pointer(cache + m.b[B_BATTLEFIELD_ROWS]);
                if (!battlefield || instance_id >= count || !rows ||
                    m.pointer(rows + sizeof(uintptr_t) * instance_id) != reinterpret_cast<uintptr_t>(battlefield))
                    throw std::runtime_error("NATIVE_CACHE_NOT_READY_STOP");
                auto dtor = m.function<One>(B_RESOURCE_REQUEST_LIST_DESTRUCTOR);
                c.invoke("ResourceRequest::destructor", [&] { dtor(request); return true; });
                std::free(request); request = nullptr;
            } else if (stage == 8) {
                if (!s.manager) throw std::runtime_error("HOST_MANAGER_MISSING");
                auto update = m.function<Update>(B_MANAGER_UPDATE);
                c.invoke("Manager::update", [&] { update(ptr(s.manager), 0.05f); return true; });
            }
        }
        ++next_stage; stopped = false;
    } catch (const std::exception& e) { fail(env, e.what()); }
    env->ReleaseStringUTFChars(token_string, token);
    return result;
}
