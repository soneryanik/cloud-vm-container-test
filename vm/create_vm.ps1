# Creates the VirtualBox VM used as alternative 1 (VM).
# Ubuntu 22.04 cloud image + cloud-init seed ISO, 2 vCPU, 2 GB RAM, NAT.
# Host port 8080 -> guest 8000 (API), host 2222 -> guest 22 (SSH).
param(
    [string]$Ova     = "D:\vbox\jammy.ova",
    [string]$Seed    = "D:\vbox\seed.iso",
    [string]$VmDir   = "D:\vbox\vms",
    [string]$VmName  = "sen421-vm"
)
# VBoxManage prints progress on stderr, so do not treat stderr as failure;
# check exit codes instead.
$ErrorActionPreference = "Continue"
$VBox = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
function Invoke-VBox { & $VBox @args 2>&1 | Out-Host; if ($LASTEXITCODE -ne 0) { throw "VBoxManage failed: $args" } }

Invoke-VBox setproperty machinefolder $VmDir
Invoke-VBox import $Ova --vsys 0 --vmname $VmName --cpus 2 --memory 2048 --eula accept
Invoke-VBox modifyvm $VmName --nic1 nat --uart1 off --audio-enabled off --graphicscontroller vmsvga
Invoke-VBox modifyvm $VmName --natpf1 "http,tcp,127.0.0.1,8080,,8000"
Invoke-VBox modifyvm $VmName --natpf1 "ssh,tcp,127.0.0.1,2222,,22"

# The OVA already defines an (empty) IDE controller; attach the seed ISO there.
Invoke-VBox storageattach $VmName --storagectl "IDE" --port 0 --device 0 --type dvddrive --medium $Seed

& $VBox showvminfo $VmName --machinereadable | Select-String '^(cpus|memory|nic1|Forwarding|"SCSI-0-0"|"IDE-0-0")'
