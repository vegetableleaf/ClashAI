package royale.nativehost;

import dalvik.system.PathClassLoader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import android.content.res.AssetManager;
import android.content.res.Resources;
import android.util.DisplayMetrics;
import android.os.StatFs;
import org.json.JSONArray;
import org.json.JSONObject;

/** Single attempt, explicit stage ceiling, no client Application or Activity. */
public final class JniHost {
    private static final String[] LIMITS = {"load-only", "create_game_main", "game_main_init",
        "data_tables_range", "data_load_tasks", "loading_state", "map_resources",
        "battlefield_cache", "manager_update"};
    private static String stage = "class_loader", token;
    private static long began;

    private static void emit(String event, Object value) throws Exception {
        long now = System.nanoTime();
        JSONObject row = new JSONObject().put("schema_version", 7).put("token", token)
            .put("pid", android.os.Process.myPid()).put("stage", stage).put("event", event)
            .put("monotonic_ns", Long.toString(now))
            .put("elapsed_ns", Long.toString(now - began))
            .put("value", value == null ? JSONObject.NULL : value);
        System.out.println("ORACLE_V7 " + row);
        System.out.flush();
    }
    private static void begin(String name) throws Exception {
        stage = name; began = System.nanoTime(); emit("before", null);
    }
    private static Object call(Class<?> stub, String name, Class<?>[] types, Object... args)
            throws Throwable {
        try { return stub.getMethod(name, types).invoke(null, args); }
        catch (InvocationTargetException e) { throw e.getCause(); }
    }
    private static JSONObject observe(Class<?> stub, String libg, long[] binding) throws Throwable {
        return new JSONObject((String) call(stub, "nativeRead",
            new Class<?>[] {String.class, long[].class}, libg, binding));
    }
    public static void main(String[] args) {
        // libg, scratch, token, APKs, native path, preload mode, stage limit, deps...
        if (args.length < 7) System.exit(64);
        token = args[2];
        Class<?> stub = null;
        long[] binding = null;
        boolean loaded = false;
        try {
            int limit = java.util.Arrays.asList(LIMITS).indexOf(args[6]);
            if (limit < 0 || !(args[5].equals("on") || args[5].equals("off")) ||
                    (args[5].equals("off") && args.length != 7))
                throw new IllegalArgumentException("HOST_ARGUMENTS");
            String libg = args[0], root = args[1];
            begin("class_loader");
            JSONObject config = new JSONObject(new String(Files.readAllBytes(
                Paths.get(root, "runtime-binding.json")), java.nio.charset.StandardCharsets.UTF_8));
            if (config.getInt("schema_version") != 7 || !config.getString("runtime_version").equals("160402012"))
                throw new IllegalStateException("HOST_BINDING_VERSION");
            JSONArray values = config.getJSONArray("values");
            binding = new long[values.length()];
            for (int i = 0; i < binding.length; ++i) binding[i] = values.getLong(i);
            long[] recipe = new long[0];
            if (!config.isNull("location_recipe")) {
                JSONObject r = config.getJSONObject("location_recipe");
                JSONArray offsets = r.getJSONArray("offsets");
                recipe = new long[offsets.length() + 2];
                recipe[0] = r.getLong("global_rva"); recipe[1] = r.getLong("vtable_rva");
                for (int i = 0; i < offsets.length(); ++i) recipe[i + 2] = offsets.getLong(i);
            }
            PathClassLoader loader = new PathClassLoader(root + "/jnihost-loader.jar:" + args[3],
                args[4], JniHost.class.getClassLoader());
            stub = Class.forName("royale.nativehost.AppLibraryLoader", false, loader);
            if (stub.getClassLoader() != loader) throw new IllegalStateException("HOST_STUB_PARENT_SHADOW");
            Thread.currentThread().setContextClassLoader(loader);
            emit("after", new JSONObject().put("stub_loader_verified", true).put("apk_paths", args[3])
                .put("native_search_path", args[4]).put("preload", args[5].equals("on")));
            begin("observer_load");
            call(stub, "loadObserver", new Class<?>[] {String.class}, root + "/libjnihost_ro.so");
            emit("after", null);
            begin("dependency_preload");
            String[] deps = java.util.Arrays.copyOfRange(args, 7, args.length);
            if (args[5].equals("on")) call(stub, "preload", new Class<?>[] {String[].class}, (Object) deps);
            emit("after", deps.length);
            begin("jni_on_load");
            call(stub, "loadGame", new Class<?>[0]); loaded = true;
            emit("after", null);
            JSONObject state = observe(stub, libg, binding);
            emit("observation", state);
            AssetManager assets = null;
            for (int i = 1; i <= limit; ++i) {
                begin(LIMITS[i]);
                emit("observation_before", observe(stub, libg, binding));
                if (i == 1) {
                    // Real framework AssetManager over the verified APK splits.
                    // No package context, app shell, fabricated callbacks or device identity.
                    assets = AssetManager.class.getDeclaredConstructor().newInstance();
                    Method add = AssetManager.class.getMethod("addAssetPath", String.class);
                    for (String apk : args[3].split(":"))
                        if (((Integer) add.invoke(assets, apk)) == 0)
                            throw new IllegalStateException("HOST_ASSET_PATH_REJECTED");
                    for (String name : new String[] {"data", "cache", "external"})
                        if (!new File(root, name).mkdir()) throw new IllegalStateException("HOST_SCRATCH_CREATE");
                }
                DisplayMetrics dm = Resources.getSystem().getDisplayMetrics();
                long available = new StatFs(root).getAvailableBytes();
                if (i == 1) emit("arguments", new JSONObject().put("activity", JSONObject.NULL)
                    .put("asset_source", "verified_installed_apks").put("available_bytes", available)
                    .put("width", dm.widthPixels).put("height", dm.heightPixels).put("density_dpi", dm.densityDpi)
                    .put("xdpi", dm.xdpi).put("ydpi", dm.ydpi).put("graphics_api", 2)
                    .put("display_source", "Resources.getSystem().getDisplayMetrics"));
                Object returned = call(stub, "nativeStage", new Class<?>[] {String.class, long[].class,
                    int.class, String.class, Object.class, String.class, String.class, String.class,
                    long.class, int.class, int.class, int.class, float.class, float.class, int.class, long[].class},
                    libg, binding, i, token, assets, root + "/data", root + "/cache", root + "/external",
                    available, dm.widthPixels, dm.heightPixels, dm.densityDpi, dm.xdpi, dm.ydpi, 2, recipe);
                emit("native_return", returned);
                state = observe(stub, libg, binding);
                emit("observation", state);
                // Nonempty CreateGameMain message is never suppressed or worked around.
                if (i == 1 && returned != null && !returned.toString().isEmpty())
                    throw new IllegalStateException("NATIVE_CREATE_MESSAGE_STOP");
                if (!state.getString("game_main_status").equals("identified"))
                    throw new IllegalStateException("HOST_GAME_MAIN_NOT_IDENTIFIED");
                if (i >= 3 && (!state.has("tables_ready") || !Boolean.TRUE.equals(state.opt("tables_ready"))))
                    throw new IllegalStateException("NATIVE_TABLES_NOT_READY_STOP");
                emit("after", new JSONObject().put("success", true));
            }
            begin("stop_after_stage_limit"); emit("boundary", args[6]);
            System.exit(0);
        } catch (Throwable error) {
            // Observation only after a caught exception; never call another native stage.
            if (loaded && stub != null && binding != null) {
                try { emit("observation_failure", observe(stub, args[0], binding)); }
                catch (Throwable ignored) { /* Preserve original failure. */ }
            }
            try { emit("error", error.getClass().getName() + ": " + error.getMessage()); }
            catch (Exception ignored) { }
            error.printStackTrace(System.err); System.err.flush(); System.exit(2);
        }
    }
}
