package royale.nativehost;

/** Defined only by the APK-aware child. No client lifecycle methods. */
public final class AppLibraryLoader {
    private AppLibraryLoader() {}
    public static void loadObserver(String path) { System.load(path); }
    public static void preload(String[] paths) {
        for (String path : paths) System.load(path);
    }
    public static void loadGame() { System.loadLibrary("g"); }
    public static native String nativeRead(String libg, long[] binding);
    public static native String nativeStage(String libg, long[] binding, int stage,
        String token, Object assets, String data, String cache, String external,
        long available, int width, int height, int density, float xdpi, float ydpi,
        int graphicsApi, long[] locationRecipe);
}
