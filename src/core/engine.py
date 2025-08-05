import os
import time
import numpy as np
import textwrap
import sounddevice as sd
import soundfile as sf
from sentence_transformers import SentenceTransformer
import faiss
import whisper
from gtts import gTTS
from playsound import playsound

# --- Configurações ---
AUDIO_FILENAME = "temp_query.wav"
RESPONSE_FILENAME = "temp_response.mp3"
MODELO_WHISPER = "base" # "tiny", "base", "small", "medium". "base" é um bom equilíbrio.
MODELO_EMBEDDING = 'distiluse-base-multilingual-cased-v1'

# --- Classe para Cores no Terminal ---
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# --- 1. SETUP INICIAL: CRIANDO A BASE DE CONHECIMENTO (RAG) ---
class KnowledgeBase:
    def __init__(self, document_text):
        print(f"{Colors.BLUE}--- Inicializando a Base de Conhecimento (RAG) ---{Colors.ENDC}")
        self.chunks = self._chunk_text(document_text)
        print(f"📄 Documento dividido em {len(self.chunks)} chunks.")
        
        print("🧠 Carregando modelo de embedding...")
        self.model = SentenceTransformer(MODELO_EMBEDDING)
        
        chunk_embeddings = self.model.encode(self.chunks)
        print(f"✅ Embeddings gerados. Dimensão do vetor: {chunk_embeddings.shape[1]}")
        
        self.index = faiss.IndexFlatL2(chunk_embeddings.shape[1])
        self.index.add(chunk_embeddings)
        print(f"⚡ Vector Store FAISS criado com {self.index.ntotal} vetores.")
        print(f"{Colors.GREEN}--- Base de Conhecimento Pronta! ---\n{Colors.ENDC}")

    def _chunk_text(self, text, chunk_size=250):
        # Estratégia de chunking simples por sentenças
        sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    def search(self, query, k=2):
        query_embedding = self.model.encode([query])
        _, indices = self.index.search(query_embedding, k)
        return [self.chunks[i] for i in indices[0]]

# --- 2. COMPONENTES DE INTERAÇÃO ---
class VoiceIO:
    def record_audio(self, duration=5, fs=16000):
        print(f"{Colors.YELLOW}🎤 Fale agora... (Gravando por {duration} segundos){Colors.ENDC}")
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
        sd.wait()
        sf.write(AUDIO_FILENAME, recording, fs)
        print(f"✅ Áudio gravado em '{AUDIO_FILENAME}'")
        return AUDIO_FILENAME

    def transcribe_audio(self, model, audio_path):
        print("🤫 Transcrevendo áudio com Whisper...")
        result = model.transcribe(audio_path)
        print(f"🗣️ Você disse: {Colors.GREEN}{result['text']}{Colors.ENDC}")
        return result['text']

    def text_to_speech(self, text):
        print("🔊 Convertendo resposta para áudio...")
        try:
            tts = gTTS(text=text, lang='pt-br', slow=False)
            tts.save(RESPONSE_FILENAME)
            print(f"▶️  Tocando resposta...{Colors.ENDC}")
            playsound(RESPONSE_FILENAME)
        finally:
            if os.path.exists(RESPONSE_FILENAME):
                os.remove(RESPONSE_FILENAME)

# --- 3. LÓGICA DE GERAÇÃO (LLM SIMULADO) ---
def mock_llm_response(query, context_chunks):
    """Simula um LLM gerando uma resposta baseada no contexto."""
    context = "\n- ".join(context_chunks)
    
    # Lógica de simulação do LLM
    # Em um sistema real, aqui você chamaria o Ollama
    if "glicose" in context or "oxigênio" in context:
        return "De acordo com meu conhecimento, a fotossíntese produz principalmente glicose, que serve como energia para a planta, e oxigênio, que é liberado na atmosfera."
    elif "cloroplastos" in context or "clorofila" in context:
        return "O processo de fotossíntese ocorre dentro de estruturas chamadas cloroplastos, que contêm clorofila, o pigmento que captura a luz solar."
    else:
        return "Não encontrei informações suficientes sobre isso na minha base de dados para dar uma resposta precisa."

# --- 4. ORQUESTRADOR PRINCIPAL ---
def main():
    # Documento para a base de conhecimento
    documento_texto = """
    A fotossíntese é um processo vital que converte luz solar, dióxido de carbono e água em glicose e oxigênio.
    A glicose é usada pela planta como energia para crescer. O oxigênio é liberado na atmosfera, sendo crucial para a respiração dos animais.
    Este processo acontece nos cloroplastos, pequenas organelas verdes dentro das células das plantas.
    A cor verde vem da clorofila, um pigmento que absorve a energia da luz solar.
    A fotossíntese tem duas fases: a fase clara, que depende da luz, e a fase escura, ou ciclo de Calvin, que usa a energia capturada para produzir a glicose.
    """
    
    # Setup inicial
    knowledge_base = KnowledgeBase(documento_texto)
    voice_io = VoiceIO()
    
    print(f"\n{Colors.BLUE}--- Carregando modelo Whisper ({MODELO_WHISPER}) ---{Colors.ENDC}")
    whisper_model = whisper.load_model(MODELO_WHISPER)
    print(f"{Colors.GREEN}--- Assistente de Voz RAG pronto! ---{Colors.ENDC}")

    try:
        while True:
            # 1. Ouvir a pergunta
            audio_path = voice_io.record_audio()
            
            # 2. Transcrever a pergunta
            user_query = voice_io.transcribe_audio(whisper_model, audio_path)
            
            if not user_query.strip():
                print(f"{Colors.RED}Não consegui ouvir nada. Tente novamente.{Colors.ENDC}")
                continue

            # 3. Buscar contexto relevante (Retrieval)
            print("🔍 Buscando informações relevantes...")
            contexto = knowledge_base.search(user_query)
            
            # 4. Gerar a resposta (Generation)
            print("🤖 Gerando resposta com base no contexto...")
            final_response = mock_llm_response(user_query, contexto)
            
            # 5. Falar a resposta
            voice_io.text_to_speech(final_response)
            
            print("\n" + "="*50 + "\n")
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Encerrando o assistente. Até mais!{Colors.ENDC}")
    finally:
        # Limpeza de arquivos temporários
        if os.path.exists(AUDIO_FILENAME):
            os.remove(AUDIO_FILENAME)
        if os.path.exists(RESPONSE_FILENAME):
            os.remove(RESPONSE_FILENAME)

if __name__ == "__main__":
    main()