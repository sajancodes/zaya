import React from 'react';

export const WindowsBetaGuide: React.FC = () => <aside style={{margin:'24px 0',padding:24,border:'1px solid #b58256',borderRadius:16,lineHeight:1.8}}>
  <h1 className="editorial-title" style={{fontSize:36}}>Windows beta installation guide</h1>
  <p>This is an early testing release, created by Sajan Rai. It has no verified Windows publisher signature. Expect bugs; start with a small project and keep Full Access off while learning the controls. Automatic installation of beta updates is not supported.</p>
  <h3>1. Download and check the file</h3>
  <p>Use the Windows Beta download on this website or the linked sajancodes/zaya-companion-releases GitHub release. The file is <code>ZayaBetaSetup.exe</code>. Compare its SHA-256 with the release before opening it:</p>
  <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>Get-FileHash -Algorithm SHA256 "$HOME\Downloads\ZayaBetaSetup.exe"</pre>
  <p>A matching checksum checks the file against the published download; it does not replace a publisher signature or a malware scan. If the checksum differs, stop and download again from the official release.</p>
  <h3>2. Understand Windows warnings</h3>
  <p>“Unknown publisher” or “Windows protected your PC” can appear because this beta is unsigned and has no established reputation. If Windows offers “More info”, it shows the file and publisher details. Decide whether to continue only after checking the official source and checksum.</p>
  <p><strong>If Windows reports a named threat, blocks the file with Smart App Control, or your workplace policy prevents installation, stop.</strong> Do not turn off antivirus, Smart App Control, or other protections. Report the exact message without sending keys, private conversations, or personal files. Some devices cannot run this unsigned beta.</p>
  <p><a href="https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions" target="_blank" rel="noopener noreferrer">Microsoft: how Smart App Control handles unsigned apps</a></p>
  <h3>3. Install and launch</h3>
  <p>The screenshots below show the actual beta installer. Choose a folder, keep Coding Skill unchecked unless you want optional OpenCode installation, and review the summary. The default folder is <code>%LOCALAPPDATA%\Programs\ZayaBeta</code>. No administrator access is required for the base app.</p>
  <figure><img src="/assets/install/windows-beta-options.png" alt="Actual Zaya Beta installer options showing optional desktop shortcut and Coding Skill" loading="lazy" style={{width:'100%',maxWidth:680,borderRadius:10}}/><figcaption>Optional setup tasks. Coding Skill is not required for normal assistant use.</figcaption></figure>
  <figure><img src="/assets/install/windows-beta-ready.png" alt="Actual Zaya Beta installer summary before installation" loading="lazy" style={{width:'100%',maxWidth:680,borderRadius:10}}/><figcaption>Review the installation summary before continuing. Your chosen path may differ.</figcaption></figure>
  <h3>4. Configure your provider and microphone</h3>
  <p>Open Zaya from the Start menu. Use your own provider credentials in the first-run setup. Provider access, quotas and possible charges are separate from the Zaya download. Keep API keys private. A microphone and network connection are required for cloud voice features; camera and phone pairing are optional.</p>
  <figure><img src="/assets/install/windows-beta-first-run.png" alt="Actual first-run screen from a fresh Zaya testing profile with no personal credentials" loading="lazy" style={{width:'100%',maxWidth:780,borderRadius:10}}/><figcaption>First run in a fresh testing profile. No personal credentials are shown.</figcaption></figure>
  <h3>If something does not work</h3>
  <ul>
    <li><strong>No voice:</strong> select the correct microphone/speaker, check Windows microphone permission yourself, and test your provider connection and quota.</li>
    <li><strong>No window:</strong> check the system tray and avoid starting multiple copies. Restart Zaya once. If it still fails, report the startup error and beta version.</li>
    <li><strong>Camera or phone unavailable:</strong> enable only the feature you need, check device permissions and pairing, and confirm the phone can reach the laptop. The desktop must be available for companion features.</li>
    <li><strong>Missing DLL or startup exception:</strong> report the exact error. Do not download replacement DLLs from third-party sites.</li>
    <li><strong>Updating:</strong> download the next beta manually from the official release, close Zaya, and run its installer. Back up your local data first. The signed automatic updater will not install unsigned betas.</li>
    <li><strong>Uninstalling:</strong> use Windows Installed apps. Choose No when asked whether to remove local Zaya data if you want to keep your configuration and history.</li>
  </ul>
  <p>Report reproducible problems to <a href="mailto:ab4290025@gmail.com">ab4290025@gmail.com</a> with your Windows version, Zaya beta version, steps and a redacted screenshot. This is a limited beta, not a fully verified stable release.</p>
</aside>;
