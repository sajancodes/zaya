# Google Play Console & Play Protect Release Checklist

This guide provides the complete developer operational checklist for registering, signing, submitting, and establishing Play Protect reputation for **Zaya Companion** (`com.zaya.companion`).

---

## 1. Google Play Console Developer Account Setup

1. **Account Registration**:
   - Navigate to [Google Play Console](https://play.google.com/console).
   - Register as an Individual or Organization developer.
   - Pay the one-time $25 USD registration fee using the owner's authorized payment method.
2. **Identity Verification**:
   - Provide government-issued photo ID (passport / national ID / driver's license).
   - Provide proof of address (utility bill / bank statement matching the registered account name).
   - Provide a working D-U-N-S number (if registering as an organization).
   - Complete 2-factor authentication on the developer Google account.

---

## 2. App Creation & Package Name Registration

1. In Play Console, click **Create app**.
2. **App details**:
   - App name: `Zaya Companion`
   - Default language: `English (United States)`
   - App or game: `App`
   - Free or paid: `Free`
3. Confirm package name:
   - Must match `com.zaya.companion` defined in `mobile/android/app/build.gradle.kts`.

---

## 3. Play App Signing Architecture & Keystore Separation

Google Play requires modern apps to enroll in **Play App Signing**:

### Upload Key vs. App Signing Key
```text
[Local Machine / CI]
  Zaya source code + Gradle :app:bundleRelease
         │
         ▼
  Signed with Upload Key (.jks / secrets.ZAYA_ANDROID_KEYSTORE_BASE64)
         │
         ▼
  Zaya-Companion.aab uploaded to Play Console
         │
         ▼
[Google Play Cloud]
  Google verifies Upload Key signature
  Google strips upload key signature
  Google re-signs app with Google-managed App Signing Key
  Google derives optimized split APKs for user devices
```

- **Upload Key**: Held securely in GitHub Actions secrets (`ZAYA_ANDROID_KEYSTORE_BASE64`) and owner's local developer machine. If lost, it can be reset via Google Play Console support.
- **App Signing Key**: Held securely inside Google Key Management Service. Users downloading from Play Store receive APKs signed with this key.
- **Standalone APK**: Builds distributed via GitHub Releases (`Zaya-Companion.apk`) are signed directly with the owner's release key.

---

## 4. Google Play Protect Reputation & Trust

### Why New Apps Trigger Play Protect Warnings
Google Play Protect scans applications using cloud intelligence, machine learning models, and telemetry. New applications, or APKs downloaded directly from the web with low download volume and no prior reputation, can trigger:
- *"Unsafe app blocked"* or
- *"Blocked by Play Protect: App is unrecognized"*

### Establishing Trust
There is no code workaround to bypass Play Protect. Trust is built through:
1. **Developer Identity Verification**: Google verifies the developer account identity.
2. **Consistent Signing Identity**: Always use the same signing key across all releases.
3. **Play Store Distribution**: Apps installed through Google Play are automatically recognized by Play Protect.
4. **Volume & Telemetry**: As users safely install and run the application over time, Play Protect records clean telemetry and ceases warning.
5. **False Positive Submission**:
   - If a standalone APK is falsely flagged by Play Protect, submit an appeal via:
     `https://support.google.com/googleplay/android-developer/contact/protectappeals`
   - Provide the APK SHA-256 fingerprint, developer contact, and explanation of application purpose.

---

## 5. Universal APK Inspection with bundletool

To verify the Android App Bundle (`.aab`) locally before uploading to Play Console:

1. Download `bundletool.jar` from [GitHub bundletool releases](https://github.com/google/bundletool/releases).
2. Generate an APK set (`.apks`) from `Zaya-Companion.aab`:
   ```bash
   java -jar bundletool.jar build-apks \
     --bundle=dist/android-release/Zaya-Companion.aab \
     --output=dist/android-release/Zaya-Companion.apks \
     --mode=universal
   ```
3. Extract the universal APK:
   ```bash
   unzip -p dist/android-release/Zaya-Companion.apks universal.apk > dist/android-release/universal.apk
   ```
4. Verify the package and signatures:
   ```bash
   apksigner verify --verbose dist/android-release/universal.apk
   ```

---

## 6. Permissions Audit & Policy Declarations

Google Play Console requires specific justifications and declarations in the **App content** section for sensitive permissions:

| Permission | Category | Purpose in Zaya | Play Policy Requirement |
|---|---|---|---|
| `RECORD_AUDIO` | Microphone | Voice commands & real-time conversational agent | Disclose in Data Safety; prominent disclosure before request |
| `CAMERA` | Camera | Spatial vision, video queries, and companion lens | Optional hardware feature (`android.hardware.camera` required=false) |
| `FOREGROUND_SERVICE_*` | Background Service | Continuous voice stream, real-time sync with desktop | Declare foreground service types in manifest and provide video demonstration if requested |
| `READ_PHONE_STATE`, `READ_CALL_LOG`, `CALL_PHONE` | Telephony | Cellular call notifications & call handling on behalf of owner | Sensitive Permission Declaration form; default phone/assistant handler policy compliance |
| `READ_CONTACTS` | Contacts | Looking up contact names for incoming calls/messages | Data safety declaration: contacts never sold or shared with 3rd parties |
| `POST_NOTIFICATIONS` | Notifications | Call alerts, voice responses, and system status | Runtime permission requested on Android 13+ |
| `SYSTEM_ALERT_WINDOW` | Overlay | Incoming call screen and full-screen companion HUD | Special app access declaration |
| `REQUEST_INSTALL_PACKAGES` | Updates | In-app updates for standalone GitHub distribution | Play Store build automatically handles updates via Play Store; `AppUpdates.kt` disables direct install if source is `com.android.vending` |

---

## 7. Required Store Listing Assets

Prepare the following assets before submitting for review:
1. **App icon**: 512 x 512 px, 32-bit PNG, max 1024 KB.
2. **Feature graphic**: 1024 x 500 px, JPG or 24-bit PNG.
3. **Phone screenshots**: Minimum 4 screenshots, 16:9 or 9:16 aspect ratio (minimum 1080px on shortest side).
4. **Short description**: Up to 80 characters (e.g. `Your private spatial AI assistant companion`).
5. **Full description**: Up to 4000 characters detailing features, privacy guarantees, and desktop connection.
6. **Privacy Policy URL**: Hosted HTTPS URL detailing:
   - What data is collected (audio, video, telephony)
   - How data is processed (strictly locally on laptop / private owner server)
   - Data retention and deletion policies
7. **Data Safety Form**:
   - Audio: Collected for voice interface, not shared with third parties, processed ephemerally.
   - Contact info: Processed locally for owner caller ID, not transmitted to external advertising networks.

---

## 8. Release Tracks and Rollout Strategy

1. **Internal Testing Track**:
   - Add owner and trusted testers by email.
   - Immediate availability without full Google Play review.
   - Test installation, updates, and microphone/camera operations.
2. **Closed Testing Track (Alpha/Beta)**:
   - Required by Google for new personal developer accounts (20 testers for 14 days minimum).
3. **Production Track**:
   - Submit for Google Play Store review.
   - Typical review duration: 1 to 7 business days.
   - Once approved, proceed with staged rollout (10% -> 25% -> 100%).
