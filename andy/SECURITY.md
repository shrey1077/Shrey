# How Andy protects your financial data

Andy holds your income, spending, tax status and a Gmail app password, so it is built to assume the
worst about everything around it. This page sets out exactly what it defends against and what no
app can defend against, so you can judge the risk yourself.

## What's in place

| Layer | What Andy does |
|---|---|
| **Encryption at rest** | Everything lives in one file, `%LOCALAPPDATA%\Andy\vault.andy`, encrypted with AES-256-GCM. Andy writes nothing in plaintext: no log, no export, no temp file. The window runs in private mode. GCM also detects any tampering with the file. |
| **Passphrase** | Never stored. It's stretched with scrypt (about 128 MB of memory per guess), which makes guessing slow and expensive even on dedicated hardware. Andy refuses weak passphrases. |
| **Bound to this PC** | The key also needs a device secret sealed with Windows DPAPI, which only your Windows account on this PC can unseal. A copied vault file is useless on any other machine, even with the passphrase. |
| **Recovery code** | Shown once, for writing on paper. It's the only other way in, and it re-binds the vault to a new PC. About 198 bits, so it can't be guessed. |
| **Auto-lock** | Andy locks after 5 minutes idle (you can set 1 to 60) and when the window closes. Locking drops the keys and decrypted data from memory, as far as Python allows. It can't guarantee every internal copy is wiped at once. |
| **Step-up checks** | Pairing Donna, disconnecting her, and approving any spend above ₹5,000 (adjustable) need your passphrase again, even while Andy is unlocked. |
| **No network listener** | Andy opens no ports and runs no web server. The interface loads from memory into a native window. |
| **One outbound connection** | `imap.gmail.com:993` only, over verified TLS 1.2+. Read-only: the mailbox is opened with IMAP EXAMINE and messages are fetched with PEEK, so nothing is marked read, moved or deleted. |
| **Spoofed emails** | An alert counts only if it comes from a known bank or card domain **and** Gmail recorded a passing DKIM or DMARC check for that domain. A fake "HDFC alert" from an attacker is ignored. |
| **Malicious email content** | The interface never turns text into HTML, and a strict Content-Security-Policy with a per-launch nonce blocks injected scripts, remote resources and network calls from the page. |
| **Screenshots** | Windows is told to keep Andy's window out of screenshots and screen recordings by other apps. |
| **Donna** | No network port. Messages are encrypted and authenticated files on this PC (AES-256-GCM, a separate key per direction). Stale, future-dated, replayed, oversized, malformed and wrong-direction messages are rejected. Donna can only *ask*. |
| **Money** | Andy never moves money and never sees your UPI PIN, card numbers or bank passwords. The payment itself always happens in your UPI app, behind your PIN. |
| **Supply chain** | Every dependency is pinned to an exact version and SHA-256 hash, and pip refuses anything that doesn't match. |
| **GitHub** | The vault lives outside the repository, and a commit hook blocks anything that looks like a PAN or an Aadhaar number. |
| **Single instance** | A lock file stops two copies of Andy writing the vault at once. Every save is atomic, and the previous encrypted version is kept as `vault.bak`. |

## What this means if someone breaks in

- **They steal your laptop, or copy the vault file:** they get ciphertext. Off this PC it can't be
  opened at all. On this PC, while Andy is locked, they still need your passphrase, and each guess
  costs about 128 MB of memory and a noticeable fraction of a second.
- **They get into your Windows account while Andy is locked:** same as above. The vault stays sealed
  until someone types the passphrase.
- **Malware runs as you while Andy is unlocked, or captures your keystrokes:** no app can fully
  protect against this. Software running as you can read what's on your screen and in memory, and a
  keylogger can capture the passphrase. Auto-lock, screen-capture blocking and step-up checks narrow
  the window, but they can't close it. The defences here are Windows itself:
  - Keep Windows and Defender updated.
  - Turn on **BitLocker / Device encryption**.
  - Use **Windows Hello** to sign in.
  - Don't install software you don't trust.
  - Ideally, use a standard (non-administrator) Windows account day to day.
- **They take over the PC as administrator:** they control everything, as with any app on any
  machine. Lock Andy when you step away, and the data at rest stays encrypted.

## The Gmail app password

Google app passwords give IMAP access to the whole mailbox. Andy uses it only to read alert emails,
and keeps it inside the encrypted vault. You can revoke it at any time at
myaccount.google.com/apppasswords, and Andy's "Disconnect" button erases it from the vault. Google's
OAuth with a read-only scope would be narrower. It needs a Google Cloud project, so it's a possible
later upgrade.

## Reporting a problem

If you spot something Andy does that weakens any of this, open an issue in this repository
**without** including any personal or financial data.
