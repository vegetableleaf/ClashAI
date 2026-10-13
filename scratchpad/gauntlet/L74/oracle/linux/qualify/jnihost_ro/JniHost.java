package royale.nativehost;

import dalvik.system.PathClassLoader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import org.json.JSONObject;

/** One load-only attempt. No client context, component or lifecycle calls. */
public final class JniHost {
    private static String stage = "class_loader";
    private static String token;

    private static void emit(String event, Object value) throws Exception {
        JSONObject row = new JSONObject();
        row.put("schema_version", 2);
        row.put("token", token);
        row.put("pid", android.os.Process.myPid());
        row.put("stage", stage);
        row.put("event", event);
        row.put("value", value == null ? JSONObject.NULL : value);
        System.out.println("ORACLE_V6 " + row.toString());
        System.out.flush();
    }

    private static void begin(String name) throws Exception {
        stage = name;
        emit("before", null);
    }

    private static Object call(Class<?> stub, String name, Class<?>[] types, Object... args)
            throws Throwable {
        Method method = stub.getMethod(name, types);
        try { return method.invoke(null, args); }
        catch (InvocationTargetException error) { throw error.getCause(); }
    }

    public static void main(String[] args) {
        // libg, scratch, token, APK path list, native search path, preload mode,
        // followed by validated absolute dependency paths (only in opt-in mode).
        if (args.length < 6) System.exit(64);
        String libg = args[0];
        String root = args[1];
        token = args[2];
        try {
            if (!(args[5].equals("off") || args[5].equals("on")) ||
                    (args[5].equals("off") && args.length != 6))
                throw new IllegalArgumentException("HOST_PRELOAD_ARGUMENTS");
            begin("class_loader");
            ClassLoader parent = JniHost.class.getClassLoader();
            // The stub DEX must NOT be on CLASSPATH: parent-first delegation
            // would otherwise give System.loadLibrary the wrong namespace.
            PathClassLoader loader = new PathClassLoader(
                root + "/jnihost-loader.jar:" + args[3], args[4], parent);
            Class<?> stub = Class.forName("royale.nativehost.AppLibraryLoader", false, loader);
            if (stub.getClassLoader() != loader)
                throw new IllegalStateException("HOST_STUB_PARENT_SHADOW");
            // Also support libraries that explicitly consult the context loader.
            Thread.currentThread().setContextClassLoader(loader);
            emit("after", new JSONObject().put("stub_loader_verified", true)
                .put("apk_paths", args[3]).put("native_search_path", args[4])
                .put("preload", args[5].equals("on")));
            begin("observer_load");
            // Same namespace as libg: RTLD_NOLOAD must not search the host's
            // separate namespace. The read-only JNI method belongs to the stub.
            call(stub, "loadObserver", new Class<?>[] {String.class}, root + "/libjnihost_ro.so");
            emit("after", null);
            begin("dependency_preload");
            String[] paths = java.util.Arrays.copyOfRange(args, 6, args.length);
            if (args[5].equals("on"))
                call(stub, "preload", new Class<?>[] {String[].class}, (Object) paths);
            emit("after", paths.length);
            begin("jni_on_load");
            call(stub, "loadGame", new Class<?>[0]);
            emit("after", null);
            emit("observation", new JSONObject((String) call(stub, "nativeRead",
                new Class<?>[] {String.class}, libg)));
            begin("stop_after_library_load");
            emit("boundary", "load-only; no client lifecycle or native startup calls");
            System.exit(0);
        } catch (Throwable error) {
            try { emit("error", error.getClass().getName() + ": " + error.getMessage()); }
            catch (Exception ignored) { /* retain the original error below */ }
            error.printStackTrace(System.err);
            System.err.flush();
            System.exit(2);
        }
    }
}
