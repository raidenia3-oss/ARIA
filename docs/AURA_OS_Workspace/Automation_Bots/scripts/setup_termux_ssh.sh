#!/bin/bash
# Script de configuracion inicial para Termux (actualizado 2026-07-30)
# Ejecutar en Termux: bash setup_termux_ssh.sh

echo "🚀 Configurando SSH en Termux..."

# 1. Instalar OpenSSH
echo "📦 Instalando OpenSSH..."
pkg install -y openssh

# 2. Configurar SSH (generar claves del host si no existen)
echo "🔑 Configurando claves del host..."
ssh-keygen -A

# 3. Configurar contraseña para el usuario actual (si no tiene)
echo "🔐 Configurando acceso..."
echo "Por favor, establece una contraseña para el usuario actual (u0_a252):"
passwd

# 4. Iniciar el servicio SSH en el puerto 8022
echo "🌐 Iniciando servicio SSH en puerto 8022..."
sshd -p 8022

# 5. Mostrar la IP actual del dispositivo
echo "📡 Informacion de red:"
echo "   IP local: $(hostname -I)"
echo "   Interfaces de red:"
ifconfig 2>/dev/null || ip addr show

# 6. Mostrar el fingerprint de la clave del host
echo "🔒 Fingerprint del host:"
ssh-keygen -lf /data/data/com.termux/files/usr/etc/ssh/ssh_host_rsa_key.pub

# 7. Crear directorio .ssh si no existe
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 8. Instrucciones para agregar la clave publica
echo ""
echo "📋 INSTRUCCIONES PARA AGREGAR LA CLAVE PUBLICA DE LA PC:"
echo "============================================================"
echo "1. En la PC, ejecuta:"
echo "   type C:\\Users\\User\\.ssh\\id_rsa.pub"
echo ""
echo "2. Copia el contenido de la clave publica."
echo ""
echo "3. En Termux, ejecuta:"
echo "   echo 'CLAVE_PUBLICA_AQUI' >> ~/.ssh/authorized_keys"
echo "   chmod 600 ~/.ssh/authorized_keys"
echo ""
echo "4. Verifica que el servicio SSH este corriendo:"
echo "   ps aux | grep sshd"
echo ""
echo "5. Verifica que el puerto 8022 este abierto:"
echo "   netstat -tlnp | grep 8022"

echo ""
echo "✅ Configuracion completada."
echo "📌 Anota la IP de Termux y asegurate de que la PC pueda conectarse a ella."
