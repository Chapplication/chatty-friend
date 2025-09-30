# Chatty Friend Embedding Manager
# Finley 2025

import pickle
import os
from chatty_config import VECTOR_CACHE_PATH
import time
import numpy as np

class ChattyEmbed(object):

    def __init__(self, master_state, vocab):
        self.master_state = master_state

        self.vocabs = {}
        self.error = None
        saved_vocabs = {}

        # try to load the embeddings from cache
        try:

            with open(VECTOR_CACHE_PATH, 'rb') as index_file:
                saved_vocabs = pickle.load(index_file)

            # if no vocab provided, assume cache is right
            if vocab is None:
                self.vocabs = saved_vocabs
            # consider reloading with new vocabs
            elif "user_phrases" in saved_vocabs and len(saved_vocabs["user_phrases"])==len(vocab) and all([phrase in saved_vocabs["user_phrases"] for phrase in vocab]):
                if all([vector is not None for vector in saved_vocabs["vectors"]]):
                    self.vocabs = saved_vocabs

        except Exception as e:
            self.error = str(e)
            print(e)

        # if we could not load the vocabs from cache and we have some new ones from the user, build the cache
        if not self.vocabs and vocab:
            try:
                print("Reloading embeddings!")
                self.vocabs = {"user_phrases":[], "vectors":[]}

                # re-use any embeddings we already have
                missing_embeddings = []
                if "user_phrases" not in saved_vocabs:
                    missing_embeddings = vocab
                else:
                    for phrase in vocab:
                        found = False
                        if phrase in saved_vocabs["user_phrases"]:
                            phrase_ix = saved_vocabs["user_phrases"].index(phrase)
                            if len(saved_vocabs["vectors"])>phrase_ix and saved_vocabs["vectors"][phrase_ix] is not None:
                                self.vocabs["user_phrases"].append(phrase)
                                self.vocabs["vectors"].append(saved_vocabs["vectors"][phrase_ix])
                                found = True
                        if not found:
                            missing_embeddings.append(phrase)
                if missing_embeddings:

                    missing_vectors = self.get_embeddings(missing_embeddings)
                    if missing_vectors and len(missing_vectors)==len(missing_embeddings) and not any([v is None for v in missing_vectors]):
                        self.vocabs["user_phrases"].extend(missing_embeddings)
                        self.vocabs["vectors"].extend(missing_vectors)

                    # write the index file
                    with open(VECTOR_CACHE_PATH, 'wb') as index_file:
                        pickle.dump(self.vocabs, index_file)

                self.error = None

            except Exception as e:
                print(e)
                self.error = str(e)
                self.vocabs = {}

    def embedding_prep_strip(self, phrase):
        return phrase.replace("\n"," ").replace("\t"," ").replace("\r"," ").strip()

    def get_embeddings(self, phrases):

        ret = []
        try:

            chunk_size = 100
            sleep_time = 2
            max_retries = 7
            for start_index in range(0,len(phrases),chunk_size):
                for retries in range(max_retries):

                    embedding_result = self.master_state.openai.embeddings.create(model=self.master_state.conman.get_config("EMBEDDING_MODEL"), input=phrases[start_index:start_index+chunk_size])
                    if embedding_result:
                        response = [d.embedding for d in embedding_result.data]
                        if response:
                            ret.extend(response)
                            break

            if len(ret)==len(phrases):
                return [np.float32(a) for a in ret]

            # exceeded retries... API is failing
            print("Failed to retrieve embeddings for "+str(len(phrases))+" phrases")
            print(len(ret),len(phrases))
            return None

        except Exception as e:
            print("Chatty Embed: get_embeddings Exception "+str(e))
            return None

    #
    #    fast in-mem embedding match
    #
    def match(self, word, thresh=None, top_n=None, with_scores=False):

        if not self.vocabs:
            return None
        try:
            if thresh is None:
                thresh = 0.8
            if top_n is None:
                top_n = 1

            if word in self.vocabs["user_phrases"]:
                return [word] if not with_scores else [(word, 1)]

            word = self.embedding_prep_strip(word)
            if not word:
                return None

            phrase_vectors = self.get_embeddings([word])
            if not phrase_vectors or len(phrase_vectors)!=1:
                return None
            phrase_vectors = np.array(phrase_vectors).T
            d = np.dot(self.vocabs["vectors"],phrase_vectors).T
            arg_sort = d.argsort(axis=1)[0][::-1]

            ret = []
            arg_ix = 0
            while len(ret)<top_n and len(arg_sort)>arg_ix and d[0][arg_sort[arg_ix]]>thresh:
                if not with_scores:
                    ret.append(self.vocabs["user_phrases"][arg_sort[arg_ix]])
                else:
                    ret.append((self.vocabs["user_phrases"][arg_sort[arg_ix]],d[0][arg_sort[arg_ix]]))
                arg_ix+=1

            return ret

        except Exception as e:
            print(e)

        return None