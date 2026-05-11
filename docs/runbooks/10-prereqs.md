# Step 10 — Hardware + OS prep

Per node — repeat for `m75q-01`, `m75q-02`, `m75q-03`.

## 10.1 BIOS

Boot the m75q, hit **F1** during the Lenovo splash:

| Setting | Value |
|---|---|
| Boot → Secure Boot | Disabled (k8s container runtimes need cgroup v2; SB sometimes blocks the kernel modules) |
| Boot → Boot Mode | UEFI |
| Power → After Power Loss | Power On |
| Power → Wake on LAN | Enabled |
| CPU → SVM Mode | Enabled (lets nested VMs / cri-o use kvm) |

Save + reboot.

## 10.2 OS install — Ubuntu Server 24.04 LTS

Use the **server** (no GUI) ISO. During the installer:

| Prompt | Answer |
|---|---|
| Hostname | `m75q-01` (`-02`, `-03` on the others) |
| Username | `wolfgangm` (or your standard homelab admin) |
| OpenSSH | Enable |
| Snaps | None |
| Disk | Use entire disk, **no LVM** (Longhorn manages its own volumes) |

After first boot, log in and update:

```bash
sudo apt update && sudo apt -y full-upgrade
sudo apt -y install curl ca-certificates gnupg jq htop tmux open-iscsi nfs-common
sudo systemctl enable --now iscsid    # required by Longhorn
sudo timedatectl set-timezone Europe/Berlin
sudo timedatectl set-ntp true
```

Disable swap (k8s prerequisite):

```bash
sudo swapoff -a
sudo sed -i.bak '/ swap / s/^/#/' /etc/fstab
```

## 10.3 Network — static IPs on the homelab LAN

Edit `/etc/netplan/00-installer-config.yaml`. Adjust the interface name
(`enp1s0` on m75q is typical) and the IPs to whatever your LAN uses.

```yaml
network:
  version: 2
  ethernets:
    enp1s0:
      addresses: [192.168.10.11/24]   # .12 on node 2, .13 on node 3
      routes:
        - to: default
          via: 192.168.10.1
      nameservers:
        addresses: [192.168.10.1, 1.1.1.1]
```

```bash
sudo netplan apply
```

## 10.4 ZeroTier — join the homelab network

```bash
curl -s https://install.zerotier.com | sudo bash
sudo zerotier-cli join <your-zerotier-network-id>
```

In your ZeroTier admin (`my.zerotier.com`), **authorize each node** and
give them stable IPs (e.g. `10.147.18.11`, `.12`, `.13`).

## 10.5 SSH key from your workstation

From your workstation:

```bash
ssh-copy-id wolfgangm@m75q-01
ssh-copy-id wolfgangm@m75q-02
ssh-copy-id wolfgangm@m75q-03
```

Now `ssh m75q-01` should work without a password.

## 10.6 Add the three nodes to your local `/etc/hosts`

On your workstation (and on every node), so DNS isn't a blocker:

```text
192.168.10.11  m75q-01.orbiter m75q-01
192.168.10.12  m75q-02.orbiter m75q-02
192.168.10.13  m75q-03.orbiter m75q-03

# Will be populated once Ingress is up (step 40):
192.168.10.11  brokerapp.orbiter
192.168.10.11  api.brokerapp.orbiter
192.168.10.11  mlflow.brokerapp.orbiter
192.168.10.11  grafana.brokerapp.orbiter
```

> Long-term: put the same records into your homelab DNS server
> (Pi-hole / Unbound / AdGuard Home) so every client on the LAN /
> ZeroTier resolves them.

## 10.7 Verify before continuing

```bash
for h in m75q-01 m75q-02 m75q-03; do
  echo "=== $h ==="
  ssh "$h" "hostnamectl; free -h | head -2; df -h / | tail -1; uname -r"
done
```

You should see:
- Hostname matches
- ~30 GiB free RAM
- ~250 GiB free on `/`
- Kernel 6.x

Next: [20-kubernetes.md](./20-kubernetes.md).
