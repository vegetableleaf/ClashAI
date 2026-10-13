package royale.nativehost;

import android.content.Context;
import com.supercell.titan.GameApp;
import com.supercell.titan.TitanApplication;
import java.io.File;
import java.lang.reflect.Method;
import org.json.JSONObject;

/** Single bounded probe. No service, Surface, Activity launch or game loop. */
public final class JniHost {
    private static String stage = "host_start";
    private static String token;
    private static volatile boolean unsupportedCallbackReached;
    private static native String nativeRead(String installedLibg);

    public static RuntimeException unsupportedCallback(String name) {
        unsupportedCallbackReached = true;
        String message = "HOST_UNSUPPORTED_CALLBACK:" + name;
        System.err.println(message);
        System.err.flush();
        return new UnsupportedOperationException(message);
    }

    private static void checkCallbacks() {
        if (unsupportedCallbackReached) throw new IllegalStateException("HOST_UNSUPPORTED_CALLBACK:latched");
    }

    private static void emit(String event, Object value) throws Exception {
        JSONObject row = new JSONObject();
        row.put("schema_version", 1);
        row.put("token", token);
        row.put("pid", android.os.Process.myPid());
        row.put("stage", stage);
        row.put("event", event);
        row.put("value", value == null ? JSONObject.NULL : value);
        System.out.println("ORACLE_V5 " + row.toString());
        System.out.flush();
    }

    private static void begin(String name) throws Exception {
        checkCallbacks();
        stage = name;
        emit("before", null);
    }

    private static void after(String libg) throws Exception {
        checkCallbacks();
        emit("after", null);
        emit("observation", new JSONObject(nativeRead(libg)));
    }

    // Same Android context route as upstream. This obtains assets/context; it
    // never invokes the installed Application, starts a component or loads APK dex.
    private static Context context() throws Exception {
        if (android.os.Looper.myLooper() == null) android.os.Looper.prepareMainLooper();
        Class<?> thread = Class.forName("android.app.ActivityThread");
        Method main = thread.getDeclaredMethod("systemMain");
        main.setAccessible(true);
        Object instance = main.invoke(null);
        Method getContext = thread.getDeclaredMethod("getSystemContext");
        getContext.setAccessible(true);
        Context system = (Context) getContext.invoke(instance);
        // Assets only: exclude installed client code from this host's classpath.
        return system.createPackageContext("com.supercell.clashroyale", 0);
    }

    public static void main(String[] args) {
        if (args.length != 3) System.exit(64);
        String libg = args[0];
        String root = args[1];
        token = args[2];
        try {
            begin("observer_load");
            System.load(root + "/libjnihost_ro.so");
            emit("after", null);
            begin("jni_on_load");
            // The VM, not our bridge, invokes the real JNI_OnLoad exactly once.
            System.load(libg);
            after(libg);
            begin("package_context");
            Context context = context();
            TitanApplication.bindContext(context);
            emit("after", null);
            begin("native_libraries_loaded");
            TitanApplication.nOnNativeLibrariesLoaded();
            after(libg);
            begin("application_create");
            GameApp.nOnApplicationCreate();
            after(libg);
            begin("create_game_main");
            for (String name : new String[] {"data", "cache", "external"}) {
                File dir = new File(root, name);
                if (!dir.mkdir()) throw new IllegalStateException("host scratch directory exists or cannot be created");
            }
            GameApp activityShell = new GameApp(context);
            // Same JNI descriptor and arguments as upstream invokeCreateGameMain;
            // dispatch via JNI_OnLoad registration, without a mutating bridge.
            GameApp.createGameMain(context.getAssets(), root + "/data", root + "/cache",
                root + "/external", new File(root).getUsableSpace(),
                1080, 2400, 420, 420.0f, 420.0f, 2, root + "/external", activityShell);
            after(libg);
            begin("stop_before_direct_resources_and_game_main_init");
            emit("boundary", "minimal upstream init finished; no direct-resource bindings or presentation patches enabled");
            System.exit(0);
        } catch (Throwable error) {
            try { emit("error", error.getClass().getName() + ": " + error.getMessage()); }
            catch (Exception ignored) { /* original exception remains in stderr */ }
            error.printStackTrace(System.err);
            System.err.flush();
            System.exit(2);
        }
    }
}
