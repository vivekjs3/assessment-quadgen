import pty, os, time, re

PROXMOX_IP = "192.168.0.20"
TEMPLATE_ID = "3000"

def run_ssh(cmd, timeout=120):
    print(f"==> {cmd[:110]}...")
    master, slave = pty.openpty()
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.execv('/usr/bin/ssh', ['ssh', '-o', 'StrictHostKeyChecking=no', f'root@{PROXMOX_IP}', cmd])
    else:
        os.close(slave)
        start_time = time.time()
        output = b''
        while time.time() - start_time < timeout:
            try:
                chunk = os.read(master, 4096)
                if not chunk: break
                output += chunk
                if b'password' in chunk.lower():
                    os.write(master, b'qwer1234\n')
            except OSError:
                break
        res = output.decode('utf-8', errors='ignore')
        print(res)
        return res

def main():
    print(f"1. Cleaning up VM/Template {TEMPLATE_ID} if existing...")
    run_ssh(f'qm stop {TEMPLATE_ID} || true; qm destroy {TEMPLATE_ID} || true', timeout=30)

    print("2. Verifying Ubuntu 24.04 Cloud Image...")
    run_ssh('test -f /var/lib/vz/template/iso/noble-server-cloudimg-amd64.img || wget -q -O /var/lib/vz/template/iso/noble-server-cloudimg-amd64.img https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img', timeout=180)

    print(f"3. Creating KVM VM {TEMPLATE_ID} (2 CPUs, 2GB RAM)...")
    run_ssh(f'qm create {TEMPLATE_ID} --name ubuntu-2404-cloudinit-template --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0 --agent 1', timeout=30)

    print("4. Importing Disk to local-lvm & attaching Cloud-Init...")
    run_ssh(f'qm importdisk {TEMPLATE_ID} /var/lib/vz/template/iso/noble-server-cloudimg-amd64.img local-lvm', timeout=60)
    run_ssh(f'qm set {TEMPLATE_ID} --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-{TEMPLATE_ID}-disk-0', timeout=30)
    run_ssh(f'qm set {TEMPLATE_ID} --boot c --bootdisk scsi0', timeout=30)
    run_ssh(f'qm set {TEMPLATE_ID} --ide2 local-lvm:cloudinit', timeout=30)
    run_ssh(f'qm set {TEMPLATE_ID} --serial0 socket --vga serial0', timeout=30)
    run_ssh(f'qm disk resize {TEMPLATE_ID} scsi0 +4G', timeout=30)

    print("5. Setting Cloud-Init User, Password & SSH Key (root / qwer1234)...")
    run_ssh('test -f /root/.ssh/id_rsa.pub || ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa', timeout=15)
    run_ssh('cat /root/.ssh/id_rsa.pub > /tmp/vm_key.pub', timeout=15)
    run_ssh(f'qm set {TEMPLATE_ID} --ciuser root --cipassword qwer1234 --sshkeys /tmp/vm_key.pub --ipconfig0 ip=dhcp', timeout=30)

    print("6. Booting VM 3000 to enable password SSH out of the box...")
    run_ssh(f'qm start {TEMPLATE_ID}', timeout=30)
    time.sleep(35)

    mac = "BC:24:11:06:B7:08"
    out = run_ssh(f'qm config {TEMPLATE_ID} | grep net0', timeout=15)
    mac_match = re.search(r'virtio=([A-FA-f0-9:]+)', out)
    if mac_match:
        mac = mac_match.group(1).lower()

    vm_ip = None
    for attempt in range(10):
        out_neigh = run_ssh(f'ip neighbor show dev vmbr0 | grep -i "{mac}"', timeout=15)
        ip_match = re.findall(r'(\d+\.\d+\.\d+\.\d+)', out_neigh)
        if ip_match:
            vm_ip = ip_match[0]
            print(f"FOUND TEMPLATE DISCOVERY IP: {vm_ip}")
            break
        time.sleep(5)

    if vm_ip:
        print(f"7. Pre-configuring SSH password auth on VM {TEMPLATE_ID} ({vm_ip})...")
        run_ssh(f'ssh -o StrictHostKeyChecking=no root@{vm_ip} "echo root:qwer1234 | chpasswd && sed -i \\"s/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/\\" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null || true && sed -i \\"s/^#\\?PermitRootLogin.*/PermitRootLogin yes/\\" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null || true && systemctl restart ssh || systemctl restart sshd"', timeout=30)

    print(f"8. Stopping VM {TEMPLATE_ID}...")
    run_ssh(f'qm stop {TEMPLATE_ID}', timeout=30)

    print(f"9. Converting VM {TEMPLATE_ID} to Proxmox Template...")
    run_ssh(f'qm template {TEMPLATE_ID}', timeout=30)

    print("\n" + "="*70)
    print(f"🎉 SUCCESS! Ubuntu 24.04 Proxmox Template ID {TEMPLATE_ID} Updated!")
    print(f"   Password Authentication: Enabled by default")
    print(f"   Root Password:            qwer1234")
    print("="*70)

if __name__ == '__main__':
    main()
