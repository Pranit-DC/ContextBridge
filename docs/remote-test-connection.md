# Connect a friend on a different network

Use this page during Step 3 of either the [Codex + Claude Code guide](live-agent-test.md)
or the [Pranit + Om Codex guide](live-codex-test.md).
**You** host ContextBridge on Fedora. **Friend** runs Codex or Claude Code on Windows.
For the Codex pair test, **You means Pranit** and **Friend means Om**.
These connection steps do not depend on which agent your friend uses.

Tailscale makes a private connection between your computers over the internet.
An **SSH tunnel** carries requests from your friend's `127.0.0.1:18000` to your
`127.0.0.1:8000`. ContextBridge can therefore keep its current localhost-only setup.
The API and database ports stay private; no router port forwarding is needed for this approach.

## 1. Both: install and sign into Tailscale

**You, on Fedora:** if Tailscale is not installed, use its official installer:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Open the sign-in link it prints and use your own account. If Tailscale is already connected,
keep the existing installation. See [Tailscale's Linux installation guide](https://tailscale.com/docs/install/linux).

**Friend, on Windows:** install [Tailscale for Windows](https://tailscale.com/docs/install/windows),
open it from the system tray, and sign in with your own account. Reopen PowerShell afterwards.
You do not need to share Tailscale account passwords.

## 2. You: share only your Fedora computer with your friend

1. Open the [Tailscale Machines page](https://login.tailscale.com/admin/machines).
2. Find your Fedora computer. Its name can be checked with `hostname` in your terminal.
3. Open its `…` menu, choose **Share**, then **Copy invite link**.
4. Create a single-use link and send it privately to your friend.
5. Friend opens the link and accepts it using their own Tailscale account.

On Windows, friend runs:

```powershell
tailscale status
```

Find the shared Fedora computer and record its `100.x.x.x` address as **HOST_IP**. Use the address
shown on the friend's computer. Sharing is governed by both accounts' access policies; a managed
college/company account may need its administrator's help.
These controls are covered by [Tailscale's machine-sharing instructions](https://tailscale.com/docs/features/sharing).

## 3. Friend: create an SSH key

In Windows PowerShell:

```powershell
ssh -V
```

If the command is missing, install **OpenSSH Client** from Windows Optional Features, or run the
following in an **Administrator PowerShell** and reopen your normal PowerShell afterwards:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

You need only the client on Windows. See [Microsoft's OpenSSH installation instructions](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse).

Now create a key specifically for this test:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\contextbridge_live_test" -C "contextbridge-live-test"
Get-Content "$env:USERPROFILE\.ssh\contextbridge_live_test.pub"
```

When asked for a passphrase, choose one and enter it twice. If this filename already exists,
answer `n` to the overwrite question and use that test key. Send **only the `.pub` file's line**, beginning
`ssh-ed25519`, to your teammate. The file without `.pub` is your private key; keep it on your PC.

## 4. You: allow that key to forward requests to ContextBridge

On Fedora:

```bash
sudo dnf install openssh-server
sudo systemctl start sshd
systemctl is-active sshd
whoami
```

Record the `whoami` output as **LINUX_USER** and send that username to your friend. No Linux
account password needs to be shared. `sshd` should show `active`.

Prepare your SSH folder without replacing existing keys:

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
```

Open `~/.ssh/authorized_keys` in your text editor. Keep existing lines. Append **one new line**:

```text
command="/usr/bin/false",restrict,port-forwarding,permitopen="127.0.0.1:8000" ssh-ed25519 PASTE_FRIENDS_PUBLIC_KEY_HERE contextbridge-live-test
```

Replace everything from `ssh-ed25519` onwards with the complete public-key line your friend sent.
Keep the options before it exactly as shown, with no space between the comma-separated options.
Save the file. This key denies remote commands and restricts local forwarding to the API's
address. We are using ordinary OpenSSH over Tailscale, so **do not enable Tailscale SSH** for this
walkthrough. The key options are documented in [OpenSSH's authorized_keys reference](https://man.openbsd.org/sshd.8#AUTHORIZED_KEYS_FILE_FORMAT).

Get your SSH host fingerprint:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Send the `SHA256:...` fingerprint to your friend, so they can recognize your computer at first connection.

## 5. Friend: open the tunnel and keep its window open

In PowerShell, replace `LINUX_USER` and `HOST_IP` below with the values from Steps 2 and 4.
Do not type the placeholders unchanged.

```powershell
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o IdentitiesOnly=yes -i "$env:USERPROFILE\.ssh\contextbridge_live_test" -L 127.0.0.1:18000:127.0.0.1:8000 LINUX_USER@HOST_IP
```

On the first connection, compare the fingerprint with the one your teammate sent. If it matches,
type `yes`. Enter your **SSH key passphrase** if asked, not your teammate's Linux password.

**Success:** the command stays running, usually with no further output and no new prompt.
This is normal for a tunnel. Leave this PowerShell window open throughout the test.
The command options are described in the [OpenSSH client reference](https://man.openbsd.org/ssh.1).

## 6. Friend: check that requests reach the service

Open a browser on Windows and visit:

```text
http://127.0.0.1:18000/health/live
```

**Success:** the page shows `{"status":"ok"}`. This checks the connection; the token/readiness
check in Step 4 of your chosen test guide checks database access too. Return to that guide's
Step 4 now.

## If the connection fails

- **Tailscale command not found on Windows:** reopen PowerShell after installation. If needed,
  run `& "$env:ProgramFiles\Tailscale\tailscale.exe" status`.
- **Connection refused:** check `systemctl is-active sshd` on Fedora and confirm HOST_IP.
- **Connection times out:** check Tailscale is connected on both PCs and the share was accepted.
  Custom Tailscale policies must allow the friend to reach TCP port 22 on your shared computer.
- **Fedora firewall blocks SSH:** on your own trusted test machine, find the zone containing
  `tailscale0` with `sudo firewall-cmd --get-active-zones` (use `sudo firewall-cmd --get-default-zone`
  if it is unassigned). Temporarily allow SSH in that zone with
  `sudo firewall-cmd --zone=ZONE_NAME --add-service=ssh --timeout=1h`, replacing `ZONE_NAME`.
  This permits SSH for the zone for one hour; choose the Tailscale zone when assigned. If it is a
  shared/default zone, the rule also applies to its other interfaces during that hour.
  Check `sudo firewall-cmd --zone=ZONE_NAME --query-service=ssh` first; leave an existing allowance
  unchanged. See the [firewalld command reference](https://firewalld.org/documentation/man-pages/firewall-cmd.html).
- **Permission denied (publickey):** check LINUX_USER, the selected `-i` key file, the complete
  public-key line and folder permissions. On Fedora, restore SSH file labels with
  `restorecon -R "$HOME/.ssh"`. Do not switch off SELinux or share a login password to bypass this.
- **It asks for the Linux login password:** cancel with `Ctrl+C` and fix the public-key setup.
- **Port 18000 is already in use:** choose another unused local port, such as 18001, in the
  `-L` option, browser URL, and friend's private adapter env file URL together
  (`.env.mcp.live-test` for Claude or `.env.mcp.codex-test` for Om's Codex).
- **Tunnel is running but the browser fails:** check ContextBridge is still running on Fedora
  and its local `http://127.0.0.1:8000/health/live` works. SSH server policy must permit TCP forwarding.

## After the test

1. Friend stops the tunnel with `Ctrl+C`.
2. You remove only the public-key line you added to `authorized_keys` for this test's friend.
   Match the actual public key, not just the `contextbridge-live-test` comment; another teammate
   may have used the same comment on a different key.
3. You revoke this machine's test share in the Tailscale Machines page if access is no longer needed.
4. If SSH was started only for this test and you do not otherwise use it, stop it with
   `sudo systemctl stop sshd`. Leave an already-used SSH service running.
5. An optional temporary firewall rule expires after one hour. To end it sooner, remove only the
   rule you added with `sudo firewall-cmd --zone=ZONE_NAME --remove-service=ssh`; do not remove a
   pre-existing rule.

These instructions prepare the connection; they do not establish that a live-agent test passed.
Record the actual results using your chosen test guide's checklist.
