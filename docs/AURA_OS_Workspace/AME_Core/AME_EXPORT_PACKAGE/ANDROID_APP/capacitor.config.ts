import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.aura.mobile',
  appName: 'AURA Mobile',
  webDir: 'www',
  server: {
    androidScheme: 'https',
    url: 'https://tu-tunel-cloudflare.com',
    cleartext: true
  },
  plugins: {
    BiometricAuth: {
      // Configuración específica para el plugin de biometría
    }
  }
};

export default config;
