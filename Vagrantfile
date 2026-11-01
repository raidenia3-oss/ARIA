# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile — ARIA OS Kali
# Requisitos: Vagrant + VirtualBox (o VMware/libvirt)
# Uso: vagrant up
#
# Esta VM descarga Kali Linux rolling, instala dependencias, despliega ARIA
# y configura el entorno dedicado (sin HTTP, sin puertos, usuario sin privilegios).

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  # Box de Kali Linux rolling (oficial, desde Vagrant Cloud)
  config.vm.box = "kalilinux/rolling"
  config.vm.box_version = ">= 2026.1"

  # Nombre de la VM
  config.vm.hostname = "aria-os-kali"

  # Recursos dedicados para ARIA (Ollama + PyQt5 consumen RAM)
  config.vm.provider "virtualbox" do |vb|
    vb.name = "ARIA-OS-Kali"
    vb.memory = 4096
    vb.cpus = 2
    vb.gui = true          # Interfaz gráfica (necesaria para PyQt5)
    vb.customize ["modifyvm", :id, "--vram", "128"]
    vb.customize ["modifyvm", :id, "--accelerate3d", "on"]
    vb.customize ["modifyvm", :id, "--clipboard", "bidirectional"]
    vb.customize ["modifyvm", :id, "--draganddrop", "bidirectional"]
  end

  # Red privada para acceso desde el host (opcional, solo administración)
  config.vm.network "private_network", type: "dhcp"

  # Sincronizar carpeta del proyecto AURA al guest
  config.vm.synced_folder ".", "/opt/aria-build/AURA", type: "virtualbox"

  # Copiar script de setup al guest
  config.vm.provision "file", source: "kali-aria-setup.sh", destination: "/tmp/kali-aria-setup.sh"

  # Ejecutar setup como root
  config.vm.provision "shell", inline: <<-SHELL
    set -e
    chmod +x /tmp/kali-aria-setup.sh
    bash /tmp/kali-aria-setup.sh
  SHELL

  # Mensaje final
  config.vm.post_up_message = <<-MSG
    ========================================================================
    ARIA OS Kali está listo.
    Usuario: aria (sin sudo) | Directorio: /opt/aria/ARIA_APP
    Verificación:
      vagrant ssh -c "sudo systemctl status aria-os"
      vagrant ssh -c "curl -s http://127.0.0.1:11434/api/tags"
    Reiniciar VM para autostart de ARIA (LightDM autologin).
    ========================================================================
  MSG
end
