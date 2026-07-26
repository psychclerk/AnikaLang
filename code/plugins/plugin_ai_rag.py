import os
import json
import re
import urllib.request
import urllib.error
import pickle
import glob

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class AIRagPlugin(AnikaPlugin):
    def __init__(self):
        self._ai_state = {
            "api_key": "",
            "base_url": "http://127.0.0.1:11434/v1",  # Default to Ollama
            "chat_model": "llama3.2:3b",
            "embed_model": "nomic-embed-text",
            "headers": {}
        }
        self._rag_state = {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "top_k": 5,
            "current_file": None,
            "total_pages": 0,
            "total_chunks": 0,
            "index": None,
            "chunks": [],
            "dimension": 768,
            "is_built": False
        }

    # ==========================================================================
    # LAZY LOADERS
    # ==========================================================================
    @staticmethod
    def _get_numpy():
        try:
            import numpy as np
            return np
        except ImportError:
            raise FMS_Error("RAG requires numpy. Run: pip install numpy", error_type="Import Error")

    @staticmethod
    def _get_faiss():
        try:
            import faiss
            return faiss
        except ImportError:
            raise FMS_Error("RAG requires faiss-cpu. Run: pip install faiss-cpu", error_type="Import Error")

    @staticmethod
    def _get_pypdf2():
        try:
            from PyPDF2 import PdfReader
            return PdfReader
        except ImportError:
            raise FMS_Error("RAG requires PyPDF2. Run: pip install PyPDF2", error_type="Import Error")

    # ==========================================================================
    # UNIVERSAL AI API CLIENT (OpenAI-Compatible)
    # ==========================================================================
    class _OpenAIClient:
        def __init__(self, plugin):
            self.plugin = plugin
            self.base_url = plugin._ai_state["base_url"].rstrip("/")
            self.api_key = plugin._ai_state["api_key"]
            self.chat_model = plugin._ai_state["chat_model"]
            self.embed_model = plugin._ai_state["embed_model"]
            self.headers = {"Content-Type": "application/json", "User-Agent": "AnikaLang/1.0"}
            if self.api_key:
                self.headers["Authorization"] = f"Bearer {self.api_key}"

        def _post(self, endpoint, payload, timeout=180):
            url = f"{self.base_url}{endpoint}"
            data = json.dumps(payload).encode('utf-8')
            try:
                req = urllib.request.Request(url, data=data, headers=self.headers, method='POST')
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8', errors='replace')
                raise FMS_Error(f"API Error {e.code}: {error_body}", error_type="AI API Error")
            except urllib.error.URLError as e:
                raise FMS_Error(f"Cannot connect to {self.base_url}: {e.reason}", error_type="AI API Error")

        def _get(self, endpoint, timeout=30):
            url = f"{self.base_url}{endpoint}"
            try:
                req = urllib.request.Request(url, headers=self.headers, method='GET')
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                raise FMS_Error(f"GET request failed: {str(e)}", error_type="AI API Error")

        def chat(self, messages, temperature=0.7, max_tokens=1024):
            payload = {
                "model": self.chat_model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens, "stream": False
            }
            data = self._post("/chat/completions", payload, timeout=300)
            return data["choices"][0]["message"]["content"]

        def embed(self, texts):
            np = self.plugin._get_numpy()
            payload = {"model": self.embed_model, "input": texts, "encoding_format": "float"}
            data = self._post("/embeddings", payload, timeout=300)
            embeddings = [None] * len(texts)
            for item in data.get("data", []):
                idx = item.get("index", 0)
                embeddings[idx] = item.get("embedding", [])
            dim = len(embeddings[0]) if embeddings[0] else 0
            for i, emb in enumerate(embeddings):
                if emb is None: embeddings[i] = [0.0] * dim
            return np.array(embeddings, dtype=np.float32)

        def list_models(self):
            data = self._get("/v1/models")
            return [m["id"] for m in data.get("data", [])]

    # ==========================================================================
    # RAG COMPONENTS
    # ==========================================================================
    class _PDFProcessor:
        def __init__(self): self.total_pages = 0
        def extract_text(self, file_path):
            PdfReader = AIRagPlugin._get_pypdf2()
            pages_text = []
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                self.total_pages = len(reader.pages)
                for i, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        clean = text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
                        clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', clean)
                        pages_text.append({"page": i + 1, "text": clean.strip()})
            return pages_text

    class _TextChunker:
        def __init__(self, chunk_size=1000, chunk_overlap=200):
            self.chunk_size = chunk_size; self.chunk_overlap = chunk_overlap
        def chunk_pages(self, pages_text):
            chunks = []; global_index = 0
            for page_data in pages_text:
                page_chunks = self._split_text(page_data["text"], page_data["page"], global_index)
                chunks.extend(page_chunks); global_index += len(page_chunks)
            return chunks
        def _split_text(self, text, page_num, start_index):
            chunks = []
            if len(text) <= self.chunk_size: return [{"text": text, "page": page_num, "index": start_index}]
            start = 0; chunk_idx = start_index
            while start < len(text):
                end = start + self.chunk_size
                if end < len(text):
                    best_break = end
                    for bp in ['\n\n', '\n', '. ', '! ', '? ', '; ']:
                        idx = text.rfind(bp, max(start, end - 150), end + 50)
                        if idx != -1 and idx > start: best_break = idx + len(bp); break
                    end = best_break
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({"text": chunk_text, "page": page_num, "index": chunk_idx}); chunk_idx += 1
                start = end - self.chunk_overlap
                if start >= len(text): break
            return chunks

    class _VectorStore:
        def __init__(self): self.dimension = 768; self.index = None; self.chunks = []; self.is_built = False
        def build_index(self, chunks, embeddings):
            faiss = AIRagPlugin._get_faiss()
            self.chunks = chunks; self.dimension = embeddings.shape[1]
            faiss.normalize_L2(embeddings)
            self.index = faiss.IndexFlatIP(self.dimension); self.index.add(embeddings); self.is_built = True
        def search(self, query_embedding, top_k=5):
            faiss = AIRagPlugin._get_faiss()
            if not self.is_built or len(self.chunks) == 0: return []
            faiss.normalize_L2(query_embedding)
            scores, indices = self.index.search(query_embedding, min(top_k, len(self.chunks)))
            return [(self.chunks[idx], float(score)) for score, idx in zip(scores[0], indices[0]) if 0 <= idx < len(self.chunks)]
        def save_to_disk(self, index_path, chunks_path):
            faiss = AIRagPlugin._get_faiss()
            if self.is_built:
                faiss.write_index(self.index, index_path)
                with open(chunks_path, 'wb') as f: pickle.dump(self.chunks, f)
        def load_from_disk(self, index_path, chunks_path):
            faiss = AIRagPlugin._get_faiss()
            if os.path.exists(index_path) and os.path.exists(chunks_path):
                try:
                    self.index = faiss.read_index(index_path)
                    with open(chunks_path, 'rb') as f: self.chunks = pickle.load(f)
                    self.dimension = self.index.d; self.is_built = True; return True
                except Exception: return False
            return False

    # ==========================================================================
    # PLUGIN REGISTRATION
    # ==========================================================================
    def register(self, env, interpreter):
        plugin = self

        # --- AI FUNCTIONS ---
        def ai_init(i, a):
            if len(a) > 0 and a[0]: plugin._ai_state["api_key"] = str(a[0])
            if len(a) > 1 and a[1]: plugin._ai_state["base_url"] = str(a[1])
            if len(a) > 2 and a[2]: plugin._ai_state["chat_model"] = str(a[2])
            if len(a) > 3 and a[3]: plugin._ai_state["embed_model"] = str(a[3])
            return "SUCCESS"
        def ai_chat(i, a):
            user_prompt = str(a[0])
            system_prompt = str(a[1]) if len(a) > 1 and a[1] else None
            temperature = float(a[2]) if len(a) > 2 and a[2] is not None else 0.7
            max_tokens = int(a[3]) if len(a) > 3 and a[3] is not None else 1024
            messages = []
            if system_prompt: messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})
            return plugin._OpenAIClient(plugin).chat(messages, temperature, max_tokens)
        def ai_embed(i, a):
            embs = plugin._OpenAIClient(plugin).embed([str(a[0])])
            return embs[0].tolist()
        def ai_list_models(i, a):
            return plugin._OpenAIClient(plugin).list_models()

        env.define("AI_INIT", NativeFunction("AI_INIT", -1, ai_init))
        env.define("AI_CHAT", NativeFunction("AI_CHAT", -1, ai_chat))
        env.define("AI_EMBED", NativeFunction("AI_EMBED", 1, ai_embed))
        env.define("AI_LIST_MODELS", NativeFunction("AI_LIST_MODELS", 0, ai_list_models))

        # --- RAG FUNCTIONS ---
        def rag_init(i, a):
            if len(a) > 0 and a[0]:
                try: plugin._rag_state["chunk_size"] = int(float(a[0]))
                except: pass
            if len(a) > 1 and a[1]:
                try: plugin._rag_state["chunk_overlap"] = int(float(a[1]))
                except: pass
            if len(a) > 2 and a[2]:
                try: plugin._rag_state["top_k"] = int(float(a[2]))
                except: pass
            plugin._rag_state["index"] = None; plugin._rag_state["chunks"] = []
            plugin._rag_state["is_built"] = False; plugin._rag_state["current_file"] = None
            plugin._rag_state["total_pages"] = 0; plugin._rag_state["total_chunks"] = 0
            return "SUCCESS"

        def rag_ingest_pdf(i, a):
            np = plugin._get_numpy(); faiss = plugin._get_faiss()
            file_path = str(a[0]).strip().strip('"').strip("'")
            if not os.path.exists(file_path): raise FMS_Error(f"File not found: '{file_path}'", error_type="File Error")
            chunk_size = int(a[1]) if len(a) > 1 and a[1] else plugin._rag_state["chunk_size"]
            chunk_overlap = int(a[2]) if len(a) > 2 and a[2] else plugin._rag_state["chunk_overlap"]
            base = os.path.splitext(file_path)[0]
            suffix = f"_c{chunk_size}_o{chunk_overlap}"
            idx_path, meta_path = f"{base}{suffix}.faiss", f"{base}{suffix}.pkl"
            
            vector_store = plugin._VectorStore()
            if vector_store.load_from_disk(idx_path, meta_path):
                plugin._rag_state.update({"index": vector_store.index, "chunks": vector_store.chunks, 
                                          "is_built": True, "current_file": file_path, 
                                          "total_chunks": len(vector_store.chunks)})
                try: plugin._rag_state["total_pages"] = plugin._PDFProcessor().extract_text(file_path) and plugin._PDFProcessor().total_pages
                except: pass
                return f"CACHED: {len(vector_store.chunks)} chunks"

            client = plugin._OpenAIClient(plugin)
            processor = plugin._PDFProcessor(); chunker = plugin._TextChunker(chunk_size, chunk_overlap)
            pages = processor.extract_text(file_path)
            if not pages: raise FMS_Error("No text extracted from PDF.", error_type="RAG Error")
            plugin._rag_state["total_pages"] = processor.total_pages
            chunks = chunker.chunk_pages(pages)
            if not chunks: raise FMS_Error("No chunks created.", error_type="RAG Error")

            all_embeddings = []; batch_size = 20
            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                batch_texts = [c["text"] for c in chunks[batch_start:batch_end]]
                all_embeddings.append(client.embed(batch_texts))
            embeddings = np.vstack(all_embeddings)
            vector_store.build_index(chunks, embeddings); vector_store.save_to_disk(idx_path, meta_path)
            plugin._rag_state.update({"index": vector_store.index, "chunks": vector_store.chunks, 
                                      "is_built": True, "current_file": file_path, "total_chunks": len(chunks)})
            return f"PROCESSED: {len(chunks)} chunks ({processor.total_pages} pages)"

        def rag_query(i, a):
            if not plugin._rag_state["is_built"] or len(plugin._rag_state["chunks"]) == 0:
                raise FMS_Error("Knowledge base is empty.", error_type="RAG Error")
            question = str(a[0]); top_k = int(a[1]) if len(a) > 1 and a[1] else plugin._rag_state["top_k"]
            client = plugin._OpenAIClient(plugin); np = plugin._get_numpy(); faiss = plugin._get_faiss()
            query_embedding = client.embed([question]); faiss.normalize_L2(query_embedding)
            scores, indices = plugin._rag_state["index"].search(query_embedding, min(top_k, len(plugin._rag_state["chunks"])))
            context_parts = []; pages_used = set()
            for score, idx in zip(scores[0], indices[0]):
                if 0 <= idx < len(plugin._rag_state["chunks"]):
                    chunk = plugin._rag_state["chunks"][idx]
                    context_parts.append(f"[Page {chunk['page']}] {chunk['text']}"); pages_used.add(chunk['page'])
            context = "\n---\n".join(context_parts)
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Answer based ONLY on the provided context. Cite page numbers. If unknown, say so clearly."},
                {"role": "system", "content": f"Context:\n{context}"},
                {"role": "user", "content": question}
            ]
            answer = client.chat(messages, temperature=0.3)
            return f"{answer}\n---\n📚 Sources: Pages {', '.join(map(str, sorted(pages_used)))}"

        def rag_get_stats(i, a):
            unique_pages = set(c.get("page", 0) for c in plugin._rag_state["chunks"])
            return {"chunks": len(plugin._rag_state["chunks"]), "pages": len(unique_pages), 
                    "total_pages": plugin._rag_state["total_pages"], 
                    "current_file": plugin._rag_state["current_file"] or "", 
                    "is_built": plugin._rag_state["is_built"]}

        def rag_clear(i, a):
            plugin._rag_state.update({"index": None, "chunks": [], "is_built": False, 
                                      "current_file": None, "total_pages": 0, "total_chunks": 0})
            return "CLEARED"

        def rag_delete_cache(i, a):
            if len(a) > 0 and a[0]:
                file_path = str(a[0]).strip()
                base = os.path.splitext(file_path)[0]
                suffix = f"_c{plugin._rag_state['chunk_size']}_o{plugin._rag_state['chunk_overlap']}"
                idx_path, meta_path = f"{base}{suffix}.faiss", f"{base}{suffix}.pkl"
                deleted = 0
                if os.path.exists(idx_path): os.remove(idx_path); deleted += 1
                if os.path.exists(meta_path): os.remove(meta_path); deleted += 1
                return f"DELETED {deleted} cache files for '{os.path.basename(file_path)}'"
            else:
                deleted = 0
                for pattern in ["*.faiss", "*.pkl"]:
                    for f in glob.glob(pattern):
                        if "_c" in f and "_o" in f:
                            try: os.remove(f); deleted += 1
                            except: pass
                return f"DELETED {deleted} cache files"

        def rag_ingest_text(i, a):
            np = plugin._get_numpy(); faiss = plugin._get_faiss()
            text = str(a[0]); doc_name = str(a[1]) if len(a) > 1 else "raw_text"
            chunk_size = int(a[2]) if len(a) > 2 else plugin._rag_state["chunk_size"]
            chunk_overlap = int(a[3]) if len(a) > 3 else plugin._rag_state["chunk_overlap"]
            chunker = plugin._TextChunker(chunk_size, chunk_overlap)
            chunks = chunker.chunk_pages([{"page": 1, "text": text}])
            if not chunks: return "ERROR: No chunks created"
            client = plugin._OpenAIClient(plugin)
            all_embeddings = []; batch_size = 10
            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                all_embeddings.append(client.embed([c["text"] for c in chunks[batch_start:batch_end]]))
            embeddings = np.vstack(all_embeddings)
            temp_store = plugin._VectorStore(); temp_store.build_index(chunks, embeddings)
            if plugin._rag_state["index"] is None:
                plugin._rag_state["index"] = temp_store.index; plugin._rag_state["chunks"] = temp_store.chunks
            else:
                plugin._rag_state["index"].merge_from(temp_store.index, temp_store.index.ntotal)
                plugin._rag_state["chunks"].extend(temp_store.chunks)
            plugin._rag_state["is_built"] = True; plugin._rag_state["total_chunks"] = len(plugin._rag_state["chunks"])
            return f"INGESTED {len(chunks)} chunks from '{doc_name}'"

        def rag_query_multi(i, a): return rag_query(i, a)

        env.define("RAG_INIT", NativeFunction("RAG_INIT", -1, rag_init))
        env.define("RAG_INGEST_PDF", NativeFunction("RAG_INGEST_PDF", -1, rag_ingest_pdf))
        env.define("RAG_QUERY", NativeFunction("RAG_QUERY", -1, rag_query))
        env.define("RAG_GET_STATS", NativeFunction("RAG_GET_STATS", 0, rag_get_stats))
        env.define("RAG_CLEAR", NativeFunction("RAG_CLEAR", 0, rag_clear))
        env.define("RAG_DELETE_CACHE", NativeFunction("RAG_DELETE_CACHE", -1, rag_delete_cache))
        env.define("RAG_INGEST_TEXT", NativeFunction("RAG_INGEST_TEXT", -1, rag_ingest_text))
        env.define("RAG_QUERY_MULTI", NativeFunction("RAG_QUERY_MULTI", -1, rag_query_multi))