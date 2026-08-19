import pty, os, time

def run_ssh(cmd, timeout=180):
    print(f"==> {cmd[:90]}...")
    master, slave = pty.openpty()
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.execv('/usr/bin/ssh', ['ssh', '-o', 'StrictHostKeyChecking=no', 'root@192.168.0.20', cmd])
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
    ssh_prefix = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@192.168.0.27"
    scp_prefix = "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

    print("1. Installing kubectl on VM 100...")
    run_ssh(f'{ssh_prefix} "curl -LO https://dl.k8s.io/release/v1.29.2/bin/linux/amd64/kubectl && chmod +x kubectl && mv kubectl /usr/bin/kubectl"')

    print("2. Verifying tools on VM 100...")
    run_ssh(f'{ssh_prefix} "docker --version && kind --version && kubectl version --client"')

    print("3. Copying project files to VM 100...")
    run_ssh(f'{scp_prefix} /tmp/quadgen.zip root@192.168.0.27:/tmp/quadgen.zip')
    run_ssh(f'{ssh_prefix} "mkdir -p /root/quadgen-poc && unzip -o /tmp/quadgen.zip -d /root/quadgen-poc"')

    print("4. Executing \'make up\' inside VM 100...")
    run_ssh(f'{ssh_prefix} "cd /root/quadgen-poc && make up"', timeout=300)

if __name__ == '__main__':
    main()
