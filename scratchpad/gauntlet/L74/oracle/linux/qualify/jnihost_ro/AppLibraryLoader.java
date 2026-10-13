package royale.nativehost;

/** Child-DEX-only entry point. No app classes, constructors or initializers here. */
public final class AppLibraryLoader {
    private AppLibraryLoader() {}

    public static void loadObserver(String path) {
        System.load(path);
    }

    public static void preload(String[] paths) {
        for (String path : paths) System.load(path);
    }

    public static void loadGame() {
        // Caller must be defined by the APK-aware loader, not its parent.
        System.loadLibrary("g");
    }

    public static native String nativeRead(String installedLibg);
}
