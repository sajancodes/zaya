# The wire protocol is parsed with org.json and defended by hand; nothing needs
# reflection. Keep the rules small and honest.
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# Security: Strip verbose and debug logging in release builds
# to prevent accidental leakage of diagnostic information or credentials
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
}
