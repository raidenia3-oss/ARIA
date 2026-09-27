import { useVoiceControl } from '../../hooks/useVoiceControl'
import styles from './styles.module.css'

export function JarvisVoice() {
  const { isListening, transcript, isProcessing, startListening, stopListening } = useVoiceControl()

  return (
    <div className={styles.voiceContainer}>
      <div className={`${styles.voiceButton} ${isListening ? styles.active : ''}`}>
        <button
          onClick={isListening ? stopListening : startListening}
          className={styles.button}
        >
          🎙️
        </button>
        {isListening && <div className={styles.pulse} />}
      </div>

      <div className={styles.transcriptBox}>
        <p className={styles.label}>LISTENING...</p>
        <p className={styles.transcript}>{transcript || '[Awaiting input...]'}</p>
        {isProcessing && <p className={styles.processing}>Processing...</p>}
      </div>
    </div>
  )
}