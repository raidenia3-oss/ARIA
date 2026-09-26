/**
 * Módulo para manejar la grabación de audio usando MediaRecorder API.
 */

class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.audioBlob = null;
    }

    // Solicitar permiso de micrófono
    async requestMicrophonePermission() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            return stream;
        } catch (error) {
            console.error("Error al acceder al micrófono:", error);
            throw error;
        }
    }

    // Iniciar grabación de audio
    async startRecording() {
        if (this.isRecording) {
            console.log("Ya se está grabando");
            return;
        }

        try {
            const stream = await this.requestMicrophonePermission();
            this.mediaRecorder = new MediaRecorder(stream);

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = () => {
                this.audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                this.audioChunks = [];
                this.isRecording = false;
            };

            this.mediaRecorder.start();
            this.isRecording = true;
            console.log("Grabación iniciada");
        } catch (error) {
            console.error("Error al iniciar grabación:", error);
            throw error;
        }
    }

    // Detener grabación de audio
    stopRecording() {
        if (!this.isRecording) {
            console.log("No se está grabando");
            return;
        }

        this.mediaRecorder.stop();
        this.isRecording = false;
        console.log("Grabación detenida");
    }

    // Obtener el blob de audio grabado
    getAudioBlob() {
        return this.audioBlob;
    }

    // Limpiar el grabador
    reset() {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
        this.audioChunks = [];
        this.audioBlob = null;
        this.isRecording = false;
    }
}

// Exportar instancia única del grabador
export const audioRecorder = new AudioRecorder();