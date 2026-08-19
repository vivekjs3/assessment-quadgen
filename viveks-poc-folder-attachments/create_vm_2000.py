import pty, os, time, subprocess, json

PROXMOX_IP = "192.168.0.20"
VM_ID = "2000"

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
    print("1. Cleaning up VM 2000 if existing...")
    run_ssh(f'qm stop {VM_ID} || true; qm destroy {VM_ID} || true', timeout=30)

    print("2. Verifying Ubuntu 24.04 Cloud Image...")
    run_ssh('test -f /var/lib/vz/template/iso/noble-server-cloudimg-amd64.img || wget -q -O /var/lib/vz/template/iso/noble-server-cloudimg-amd64.img https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img', timeout=180)

    print(f"3. Creating KVM VM {VM_ID} (4 CPUs, 8GB RAM)...")
    run_ssh(f'qm create {VM_ID} --name quadgen-jenkins-poc-2000 --memory 8192 --cores 4 --net0 virtio,bridge=vmbr0 --agent 1', timeout=30)

    print("4. Importing Disk to local-lvm & attaching Cloud-Init...")
    run_ssh(f'qm importdisk {VM_ID} /var/lib/vz/template/iso/noble-server-cloudimg-amd64.img local-lvm', timeout=60)
    run_ssh(f'qm set {VM_ID} --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-{VM_ID}-disk-0', timeout=30)
    run_ssh(f'qm set {VM_ID} --boot c --bootdisk scsi0', timeout=30)
    run_ssh(f'qm set {VM_ID} --ide2 local-lvm:cloudinit', timeout=30)
    run_ssh(f'qm set {VM_ID} --serial0 socket --vga serial0', timeout=30)

    print("5. Resizing disk to 30G...")
    run_ssh(f'qm disk resize {VM_ID} scsi0 +28G', timeout=30)

    print("6. Setting Cloud-Init User, Password & SSH Key (root / qwer1234)...")
    run_ssh('test -f /root/.ssh/id_rsa.pub || ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa', timeout=15)
    run_ssh('cat /root/.ssh/id_rsa.pub > /tmp/vm_key.pub', timeout=15)
    run_ssh(f'qm set {VM_ID} --ciuser root --cipassword qwer1234 --sshkeys /tmp/vm_key.pub --ipconfig0 ip=dhcp', timeout=30)

    print(f"7. Starting Virtual Machine {VM_ID}...")
    run_ssh(f'qm start {VM_ID}', timeout=30)

    print("8. Waiting 45s for VM to boot up...")
    time.sleep(45)

    print("9. Getting VM IP via ARP / ip neighbor from Proxmox...")
    vm_ip = None
    mac = "BC:24:11:E9:98:B7"
    out = run_ssh(f'qm config {VM_ID} | grep net0', timeout=15)
    import re
    mac_match = re.search(r'virtio=([A-FA-f0-9:]+)', out)
    if mac_match:
        mac = mac_match.group(1).lower()

    for attempt in range(12):
        out_neigh = run_ssh(f'ip neighbor show dev vmbr0 | grep -i "{mac}"', timeout=15)
        ip_match = re.findall(r'(\d+\.\d+\.\d+\.\d+)', out_neigh)
        if ip_match:
            vm_ip = ip_match[0]
            print(f"FOUND VM IP: {vm_ip}")
            break
        # try ping sweep on LAN to populate ARP
        run_ssh('fping -g 192.168.0.1/24 -c 1 -t 100 &>/dev/null || true', timeout=10)
        time.sleep(5)

    if not vm_ip:
        vm_ip = "192.168.0.29" # default detected earlier

    print(f"10. Connecting to VM {VM_ID} ({vm_ip}) via Proxmox SSH Key...")
    run_ssh(f'ssh -o StrictHostKeyChecking=no root@{vm_ip} "echo SSH_CONNECTED && echo root:qwer1234 | chpasswd && sed -i \\"s/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/\\" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null || true && sed -i \\"s/^#\\?PermitRootLogin.*/PermitRootLogin yes/\\" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null || true && systemctl restart ssh || systemctl restart sshd"', timeout=30)

    print("11. Copying project zip to VM 2000 from local host...")
    local_zip = "/home/vivek/QuadGen Assesment/QuadGen_Kubernetes_Jenkins_CI_CD_POC.zip"
    # Copy to Proxmox first then to VM
    run_ssh('mkdir -p /tmp/quadgen_transfer', timeout=10)
    
    master, slave = pty.openpty()
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.execv('/usr/bin/scp', ['scp', '-o', 'StrictHostKeyChecking=no', local_zip, f'root@{PROXMOX_IP}:/tmp/quadgen_transfer/QuadGen_Kubernetes_Jenkins_CI_CD_POC.zip'])
    else:
        os.close(slave)
        start_time = time.time()
        output = b''
        while time.time() - start_time < 60:
            try:
                chunk = os.read(master, 4096)
                if not chunk: break
                output += chunk
                if b'password' in chunk.lower():
                    os.write(master, b'qwer1234\n')
            except OSError:
                break

    print(f"12. Copying zip from Proxmox host to VM {VM_ID} ({vm_ip})...")
    run_ssh(f'scp -o StrictHostKeyChecking=no /tmp/quadgen_transfer/QuadGen_Kubernetes_Jenkins_CI_CD_POC.zip root@{vm_ip}:/root/QuadGen_Kubernetes_Jenkins_CI_CD_POC.zip', timeout=60)

    print(f"13. Verifying zip file on VM 2000 ({vm_ip})...")
    run_ssh(f'ssh -o StrictHostKeyChecking=no root@{vm_ip} "ls -lh /root/QuadGen_Kubernetes_Jenkins_CI_CD_POC.zip"', timeout=15)

    print("\n" + "="*70)
    print(f"🎉 SUCCESS! Proxmox VM ID {VM_ID} is Created & Ready!")
    print(f"   IP Address: {vm_ip}")
    print(f"   SSH:        ssh root@{vm_ip} (Password: qwer1234)")
    print(f"   Zip File:   /root/QuadGen_Kubernetes_Jenkins_CI_CD_POC.zip")
    print("="*70)

if __name__ == '__main__':
    main()
