
# coding: utf-8

# # Train the model using the vocabulary embedding pickle file
# - Specify FN0 to point to the correct pickle file in data folder. This pickle file should have been generated by vocabulary-embedding
# - Implementation of the "simple" model from http://arxiv.org/pdf/1512.01712v1.pdf

# In[168]:


FN = 'train-5k-64-filter-500iter' # name of the file the model weights will be saved to (train.hdf5)
FN0 = 'all-the-news_filtered-5000-vocab-embedding-glove-filter-5000' # name of the word embedding weights
FN1 = 'train-5k-64-filter-500iter' # name of the file the model weights to load from (if starting with a pre-existing model)


# In[169]:


import logging, sys
from importlib import reload
reload(logging)
logging.basicConfig(filename='train-single-gpu-5k-64-filter.log',level=logging.INFO)
logging.info('--------------Start of Log--------------')
logging.info('Data: ' + FN0)


# You should use GPU (device=cuda) but if it is busy then you always can fall back to your CPU (device=cpu)

# In[170]:


# Only if using Theano backend
import os
os.environ['THEANO_FLAGS'] = 'device=cuda,floatX=float32'


# In[171]:


import keras
keras.__version__


# Use indexing of tokens from [vocabulary-embedding](./vocabulary-embedding.ipynb) this does not clip the indexes of the words to `vocab_size`.
# 
# Use the index of outside words to replace them with several `oov` words (`oov` , `oov0`, `oov1`, ...) that appear in the same description and headline. This will allow headline generator to replace the oov with the same word in the description

# You can start training from a pre-existing model. This allows you to run this notebooks many times, each time using different parameters and passing the end result of one run to be the input of the next.
# 
# I've started with `maxlend=0` (see below) in which the description was ignored. I then moved to start with a high `LR` and then manually lowering it. I also started with `nflips=0` in which the original headlines is used as-is and slowely moved to `12` in which half the input headline was fliped with the predictions made by the model (the paper used fixed 10%)

# ### Padding and clipping of input
# Input data (`X`) holds arrays of representations of descriptions, replacing each word by its corresponding index. (X is essentially loaded from %FN0.data.pickle, the product from vocabulary-embedding file.) 
# 
# Each entry in `X` is then left padded with `empty` until the length reaches `maxlend`. Finally the entry is appended  with an `eos`. If entry length exceeds `maxlend`, the preceding part is clipped off and the rest is appended with an `eos`.
# 
# E.g. X[0] = [12, 34, 567], word2idx['<eos>'] = 1, word2idx['<empty>'] = 0
# 
# - maxlend = 6 ==> X[0] = [0, 0, 0, 12, 34, 567, 1]
# - maxlend = 3 ==> X[0] = [12, 34, 567, 1]
# - maxlend = 2 ==> X[0] = [34, 567, 1]
# 
# Labels (`Y`) are the headline words followed by `eos` and clipped or padded to `maxlenh`
# 
# =====================
# 
# made from `maxlend` description words followed by `eos`
# followed by headline words followed by `eos`
# if description is shorter than `maxlend` it will be left padded with `empty`
# if entire data is longer than `maxlen` it will be clipped and if it is shorter it will be right padded with empty.
# 
# Labels (`Y`) are the headline words followed by `eos` and clipped or padded to `maxlenh`
# 
# In other words the input is made from a `maxlend` half in which the description is padded from the left
# and a `maxlenh` half in which `eos` is followed by a headline followed by another `eos` if there is enough space.
# 
# The labels match only the second half and 
# the first label matches the `eos` at the start of the second half (following the description in the first half)

# In[172]:


maxlend = 75 # 0 - if we dont want to use description at all
maxlenh = 16
maxlen = maxlend + maxlenh
rnn_size = 64 # must be same as 160330-word-gen, paper used 600
rnn_layers = 2  # match FN1, paper used 4
logging.info('/* Setup */')
logging.info('rnn_size: '+str(rnn_size))
logging.info('rnn_layers: ' + str(rnn_layers))


# the output of the first `activation_rnn_size` nodes from the top LSTM layer will be used for activation and the rest will be used to select predicted word

# In[173]:


activation_rnn_size = 40 if maxlend else 0
logging.info('activation_rnn_size: ' + str(activation_rnn_size))


# In[174]:


# Training parameters
seed = 42
p_W, p_U, p_dense, weight_decay = 0, 0, 0, 0
optimizer = 'rmsprop'
LR = 1e-4 # Learning rate
batch_size = 64
nflips = 10

logging.info('batch size: ' + str(batch_size))
logging.info('Learning Rate: ' + str(LR))


# # Read word embedding

# In[175]:


import pickle
with open('data/%s.pickle'%FN0, 'rb') as fp:
    embedding, idx2word, word2idx, glove_idx2idx = pickle.load(fp)
vocab_size, embedding_size = embedding.shape
print('Vocabulary size (from data)', vocab_size)
print('Embedding size', embedding_size)


# In[176]:


with open('data/%s.data.pickle'%FN0, 'rb') as fp:
    X, Y = pickle.load(fp)
print('Number of descriptions:', len(X))
print('Number of headlines:', len(Y))


# In[177]:


nb_unknown_words = 10
nb_train_samples = len(X)  # Number of training samples
nb_val_samples = len(X) * 0.1 # Number of validation set
# nb_train_samples = 30000
# nb_val_samples = 3000


# In[178]:


print('number of examples',len(X),len(Y))
print('dimension of embedding space for words',embedding_size)
print('vocabulary size', vocab_size, 'the last %d words can be used as place holders for unknown/oov words'%nb_unknown_words)
print('total number of different words',len(idx2word), len(word2idx))
print('number of words outside vocabulary which we can substitue using glove similarity', len(glove_idx2idx))
print('number of words that will be regarded as unknonw(unk)/out-of-vocabulary(oov)',len(idx2word)-vocab_size-len(glove_idx2idx))


# In[179]:


for i in range(nb_unknown_words):
    idx2word[vocab_size-1-i] = '<%d>'%i


# When printing, mark words that are outside of the vocabulary with `^` at the end

# In[180]:


oov0 = vocab_size-nb_unknown_words


# In[181]:


for i in range(oov0, len(idx2word)):
    idx2word[i] = idx2word[i]+'^'


# In[182]:


from sklearn.model_selection import train_test_split
X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.1, random_state=seed)
len(X_train), len(Y_train), len(X_test), len(Y_test)


# In[183]:


del X
del Y


# In[184]:


empty = 0
eos = 1
# For printing purposes
idx2word[empty] = '_' # Change '<empty>' to '_' 
idx2word[eos] = '~'   # Change '<eos>' to '~'


# In[185]:


import numpy as np
from keras.preprocessing import sequence
from keras.utils import np_utils
import random, sys


# In[186]:


def prt(label, x):
    print(label+':', end='')
    for w in x:
        print(idx2word[w]+' ', end='')
    print()


# In[187]:


i = random.randint(0, len(X_test) - 1) # Randomly look at an entry
print('i: ', i)
print('Training Set:')
prt('H',Y_train[i]) # Headline
prt('D',X_train[i]) # Description


# In[188]:


print('Testing Set:')
prt('H',Y_test[i]) # Headline
prt('D',X_test[i]) # Description


# # Model Configuration

# In[189]:


from keras.models import Sequential
from keras.layers.core import Dense, Activation, Dropout, RepeatVector
from keras.layers.wrappers import TimeDistributed
from keras.layers.recurrent import LSTM
from keras.layers.embeddings import Embedding
from keras.regularizers import l2 #  L2 weight regularization penalty, also known as weight decay, or Ridge
from keras.optimizers import RMSprop
from keras.layers.core import Lambda
import keras.backend as K
# from keras.utils import multi_gpu_model
import tensorflow as tf


# In[190]:


# seed weight initialization
random.seed(seed)
np.random.seed(seed)


# In[191]:


regularizer = l2(weight_decay) if weight_decay else None


# ### Start with a standaed stacked LSTM, add embedding layer

# In[192]:


# TODO:
# Instantiate the base model (or "template" model)
# Doing this under a CPU device scope so that model's weights are hosted on CPU memory.
# Otherwise they may end up hosted on a GPU, which would complicate weight sharing
# with tf.device('/cpu:0'):
#     base_model = Sequential() #  Sequential model is a linear stack of layers
base_model = Sequential()
''' Embedding layer: (first layer of the model)
   - Input size = vocab_size
   - Output size = embedding size
   - Input_length = Length of input sequences, when it is constant (maxlen)
   - Weights = Seed with the GloVe word embedding weights
   - Embeddings_regularizer = 
   - Mask_zero = Indicate that input value 0 is a special "padding" value and should be masked out. 
                 This is useful when using recurrent layers which may take variable length input. 
                 If this is True then all subsequent layers in the model need to support masking or 
                 an exception will be raised.
                 If mask_zero is set to True, as a consequence, index 0 cannot be used in the vocabulary 
                 (input_dim should equal size of vocabulary + 1).
 TODO: (1) Input_dim = vocabulary + 1?
'''
base_model.add(Embedding(vocab_size, 
                    embedding_size, 
                    input_length=maxlen, 
                    weights=[embedding], 
                    embeddings_regularizer=regularizer,
                    mask_zero=True, 
                    name='embedding_1'))

# Add rnn_layers number of LSTM layers + Dropout layers
# LSTM layer
#    - Output dimension/Units: rnn_size
#    - Return sequences: Whether to return the last output in the output sequence, or the full sequence.
#    - Kernel regularizer: Regularizer function applied to the `kernel` weights matrix
#    - Recurrent regularizer: Regularizer function applied to the `recurrent_kernel` weights matrix
#    - Bias regularizer: Regularizer function applied to the bias vector
#    - Dropout: Float between 0 and 1. Fraction of the units to drop for the linear transformation of the inputs.
#    - Recurrent dropout: Float between 0 and 1. Fraction of the units to drop for the linear transformation of the recurrent state.
for i in range(rnn_layers):
    lstm = LSTM(rnn_size, 
                return_sequences=True,
                kernel_regularizer=regularizer, 
                recurrent_regularizer=regularizer,
                bias_regularizer=regularizer, 
                dropout=p_W, 
                recurrent_dropout=p_U,
                name='lstm_%d'%(i+1)
                  )
    base_model.add(lstm)
    
    # Dropout Layer: Dropout consists in randomly setting a fraction p of input units to 0 at 
    #                each update during training time, which helps prevent overfitting.
    #    - Fraction of the input units to drop = p_dense
    base_model.add(Dropout(p_dense,name='dropout_%d'%(i+1)))


# ## Context Layer
# 
# The attention mechanism is used when outputting each word in the decoder. For each output word the attention mechanism computes a weight over each of the input words that determines how much attention should be paid to that input word. The weights sum up to 1, and are used to compute a weighted average of the last hidden layers generated after processing each of the input words. This weighted average is referred to as the context.
# 
# Context is then input into the softmax layer along with the last hidden layer from the current step of decoding.
# 
# The simple context layer described in the paper splits the hidden units of the last layer from the current step of decoding into 2 sets: One set of size 50 used for computing the attention weight, and the other of size 550 fed into the softmax layer.
# 
# Context layer reduces the input just to its headline part (second half).
# For each word in this part it concatenate the output of the previous layer (RNN)
# with a weighted average of the outputs of the description part.
# 
# In this only the last `rnn_size - activation_rnn_size` are used from each output.
# 
# The first `activation_rnn_size` output is used to computer the weights for the averaging.

# In[193]:


# TODO: Explain this
def simple_context(X, mask, n=activation_rnn_size, maxlend=maxlend, maxlenh=maxlenh):
    desc, head = X[:,:maxlend,:], X[:,maxlend:,:]
    head_activations, head_words = head[:,:,:n], head[:,:,n:]
    desc_activations, desc_words = desc[:,:,:n], desc[:,:,n:]
    
    # RTFM http://deeplearning.net/software/theano/library/tensor/basic.html#theano.tensor.batched_tensordot
    # activation for every head word and every desc word
    activation_energies = K.batch_dot(head_activations, desc_activations, axes=(2,2))
    # make sure we dont use description words that are masked out
    activation_energies = activation_energies + -1e20*K.expand_dims(1.-K.cast(mask[:, :maxlend],'float32'),1)
    
    # for every head word compute weights for every desc word
    activation_energies = K.reshape(activation_energies,(-1,maxlend))
    activation_weights = K.softmax(activation_energies)
    activation_weights = K.reshape(activation_weights,(-1,maxlenh,maxlend))

    # for every head word compute weighted average of desc words
    desc_avg_word = K.batch_dot(activation_weights, desc_words, axes=(2,1))
    return K.concatenate((desc_avg_word, head_words))


# In[194]:

print(2*(rnn_size - activation_rnn_size),maxlenh,"****************************%%%%%")
if activation_rnn_size:
    """ Lambda: Used for evaluating an arbitrary expressions on an input
      - function: simple_context
      - output_shape: Expected output shape from the function. 
                      It specifies the entire shape as a function of the input shape: 
                        output_shape = f(input_shape)
      - mask (arg of simple_context): TO-DO
    """
    base_model.add(Lambda(simple_context,
                     mask = lambda inputs, mask: mask[:,maxlend:],
                     output_shape = lambda input_shape: (input_shape[0], maxlenh, 2*(rnn_size - activation_rnn_size)),
                     name='simplecontext_1'))
    
    # Dense Layer: Just your regular densely-connected NN layer (linear transformation to make the dimensions match)
    # Time Distributed: A wrapper that allows to apply a layer to every temporal slice of an input
    base_model.add(TimeDistributed(Dense(vocab_size,
                                    kernel_regularizer=regularizer, 
                                    bias_regularizer=regularizer,
                                    name = 'timedistributed_1')))

    # Activation Layer: Applies an activation function to an output
    #  - activation: using softmax
    base_model.add(Activation('softmax', name='activation_1'))


# ## Configure the model for training

# In[195]:


# parallel_model = multi_gpu_model(base_model, gpus=2) # Parallel model: distribute base_model to 2 gpu
base_model.compile(loss='categorical_crossentropy', optimizer=optimizer)

# Use Keras backend to set the learning rate of the model to LR
K.set_value(base_model.optimizer.lr,np.float32(LR))


# In[196]:


base_model.summary()


# # Load model weights if data/train.hdf5 is present
# This file will be produced after first time of running train

# In[197]:


if os.path.exists('data/%s.hdf5'%FN1):
    base_model.load_weights('data/%s.hdf5'%FN1)


# ## Test if everything looks right so far

# In[198]:


def lpadd(x, maxlend=maxlend, eos=eos):
    """left (pre) pad a description to maxlend and then add eos.
    The eos is the input to predicting the first word in the headline
    """
    assert maxlend >= 0
    if maxlend == 0:
        return [eos]
    n = len(x)
    if n > maxlend:
        x = x[-maxlend:]
        n = maxlend
    return [empty]*(maxlend-n) + x + [eos]


# In[199]:


samples = [lpadd([3]*26)]
# pad from right (post) so the first maxlend will be description followed by headline
data = sequence.pad_sequences(samples, maxlen=maxlen, value=empty, padding='post', truncating='post')


# In[200]:


np.all(data[:,maxlend] == eos)


# In[201]:


data.shape,list(map(len, samples))


# ### Generates output predictions for the input samples

# In[202]:


probs = base_model.predict(data, verbose=0, batch_size=128)
probs.shape


# # Sample generation
# ### This section describes the process of feeding the output of a decoder as the input in the next step

# Use Beam-search decoder which generates input words one at a time, at each step extending the B highest probability sequences.

# In[203]:


# variation to https://github.com/ryankiros/skip-thoughts/blob/master/decoding/search.py
def beamsearch(predict, start=[empty]*maxlend + [eos],
               k=1, maxsample=maxlen, use_unk=True, empty=empty, eos=eos, temperature=1.0):
    """return k samples (beams) and their NLL scores, each sample is a sequence of labels,
    all samples starts with an `empty` label and end with `eos` or truncated to length of `maxsample`.
    You need to supply `predict` which returns the label probability of each sample.
    `use_unk` allow usage of `oov` (out-of-vocabulary) label in samples
    """
    def sample(energy, n, temperature=temperature):
        """sample at most n elements according to their energy"""
        n = min(n,len(energy))
        prb = np.exp(-np.array(energy) / temperature )
        res = []
        for i in range(n):
            z = np.sum(prb)
            r = np.argmax(np.random.multinomial(1, prb/z, 1))
            res.append(r)
            prb[r] = 0. # make sure we select each element only once
        return res

    dead_k = 0 # samples that reached eos
    dead_samples = []
    dead_scores = []
    live_k = 1 # samples that did not yet reached eos
    live_samples = [list(start)]
    live_scores = [0]

    while live_k:
        # for every possible live sample calc prob for every possible label 
        probs = predict(live_samples, empty=empty)
        # total score for every sample is sum of -log of word prb
        cand_scores = np.array(live_scores)[:,None] - np.log(probs)
        cand_scores[:,empty] = 1e20
        if not use_unk:
            for i in range(nb_unknown_words):
                cand_scores[:,vocab_size - 1 - i] = 1e20
        live_scores = list(cand_scores.flatten())
        

        # find the best (lowest) scores we have from all possible dead samples and
        # all live samples and all possible new words added
        scores = dead_scores + live_scores
        ranks = sample(scores, k)
        n = len(dead_scores)
        ranks_dead = [r for r in ranks if r < n]
        ranks_live = [r - n for r in ranks if r >= n]
        
        dead_scores = [dead_scores[r] for r in ranks_dead]
        dead_samples = [dead_samples[r] for r in ranks_dead]
        
        live_scores = [live_scores[r] for r in ranks_live]

        # append the new words to their appropriate live sample
        voc_size = probs.shape[1]
        live_samples = [live_samples[r//voc_size]+[r%voc_size] for r in ranks_live]

        # live samples that should be dead are...
        # even if len(live_samples) == maxsample we dont want it dead because we want one
        # last prediction out of it to reach a headline of maxlenh
        zombie = [s[-1] == eos or len(s) > maxsample for s in live_samples]
        
        # add zombies to the dead
        dead_samples += [s for s,z in zip(live_samples,zombie) if z]
        dead_scores += [s for s,z in zip(live_scores,zombie) if z]
        dead_k = len(dead_samples)
        # remove zombies from the living 
        live_samples = [s for s,z in zip(live_samples,zombie) if not z]
        live_scores = [s for s,z in zip(live_scores,zombie) if not z]
        live_k = len(live_samples)

    return dead_samples + live_samples, dead_scores + live_scores


# In[204]:


def keras_rnn_predict(samples, empty=empty, model=base_model, maxlen=maxlen):
    """for every sample, calculate probability for every possible label
    you need to supply your RNN model and maxlen - the length of sequences it can handle
    """
    sample_lengths = list(map(len, samples))
    assert all(l > maxlend for l in sample_lengths)
    assert all(l[maxlend] == eos for l in samples)
    # pad from right (post) so the first maxlend will be description followed by headline
    data = sequence.pad_sequences(samples, maxlen=maxlen, value=empty, padding='post', truncating='post')
    probs = model.predict(data, verbose=0, batch_size=batch_size)
    return np.array([prob[sample_length-maxlend-1] for prob, sample_length in zip(probs, sample_lengths)])


# In[205]:


def vocab_fold(xs):
    """convert list of word indexes that may contain words outside vocab_size to words inside.
    If a word is outside, try first to use glove_idx2idx to find a similar word inside.
    If none exist then replace all accurancies of the same unknown word with <0>, <1>, ...
    """
    xs = [x if x < oov0 else glove_idx2idx.get(x,x) for x in xs]
    # the more popular word is <0> and so on
    outside = sorted([x for x in xs if x >= oov0])
    # if there are more than nb_unknown_words oov words then put them all in nb_unknown_words-1
    outside = dict((x,vocab_size-1-min(i, nb_unknown_words-1)) for i, x in enumerate(outside))
    xs = [outside.get(x,x) for x in xs]
    return xs


# In[206]:


def vocab_unfold(desc,xs):
    # assume desc is the unfolded version of the start of xs
    unfold = {}
    for i, unfold_idx in enumerate(desc):
        fold_idx = xs[i]
        if fold_idx >= oov0:
            unfold[fold_idx] = unfold_idx
    return [unfold.get(x,x) for x in xs]


# In[207]:


import sys
import Levenshtein

def gensamples(skips=2, k=10, batch_size=batch_size, short=True, temperature=1., use_unk=True):
    i = random.randint(0,len(X_test)-1)
    print('HEAD:', ' '.join(idx2word[w] for w in Y_test[i][:maxlenh]))
    print('DESC:', ' '.join(idx2word[w] for w in X_test[i][:maxlend]))
    sys.stdout.flush()
    
    print('HEADS:')
    
    x = X_test[i]
    samples = []
    if maxlend == 0:
        skips = [0]
    else:
        skips = range(min(maxlend,len(x)), max(maxlend,len(x)), abs(maxlend - len(x)) // skips + 1)
    for s in skips:
        start = lpadd(x[:s])
        fold_start = vocab_fold(start)
        sample, score = beamsearch(predict=keras_rnn_predict, start=fold_start, k=k, temperature=temperature, use_unk=use_unk)
        assert all(s[maxlend] == eos for s in sample)
        samples += [(s,start,scr) for s,scr in zip(sample,score)]

    samples.sort(key=lambda x: x[-1])
    codes = []
    for sample, start, score in samples:
        code = ''
        words = []
        sample = vocab_unfold(start, sample)[len(start):]
        for w in sample:
            if w == eos:
                break
            words.append(idx2word[w])
            code += chr(w//(256*256)) + chr((w//256)%256) + chr(w%256)
        if short:
            distance = min([100] + [-Levenshtein.jaro(code,c) for c in codes])
            if distance > -0.6:
                print(score, ' '.join(words))
        #         print '%s (%.2f) %f'%(' '.join(words), score, distance)
        else:
                print(score, ' '.join(words))
        codes.append(code)


# In[208]:


gensamples(skips=2, batch_size=batch_size, k=10, temperature=1.)


# # Data generator

# Data generator generates batches of inputs and outputs/labels for training. The inputs are each made from two parts. The first maxlend words are the original description, followed by `eos` followed by the headline which we want to predict, except for the last word in the headline which is always `eos` and then `empty` padding until `maxlen` words.
# 
# For each, input, the output is the headline words (without the start `eos` but with the ending `eos`) padded with `empty` words up to `maxlenh` words. The output is also expanded to be y-hot encoding of each word.

# To be more realistic, the second part of the input should be the result of generation and not the original headline.
# Instead we will flip just `nflips` words to be from the generator, but even this is too hard and instead
# implement flipping in a naive way (which consumes less time.) Using the full input (description + eos + headline) generate predictions for outputs. For nflips random words from the output, replace the original word with the word with highest probability from the prediction.

# In[209]:


def flip_headline(x, nflips=None, model=None, debug=False):
    """given a vectorized input (after `pad_sequences`) flip some of the words in the second half (headline)
    with words predicted by the model
    """
    if nflips is None or model is None or nflips <= 0:
        return x
    
    batch_size = len(x)
    assert np.all(x[:,maxlend] == eos)
    probs = model.predict(x, verbose=0, batch_size=batch_size)
    x_out = x.copy()
    for b in range(batch_size):
        # pick locations we want to flip
        # 0...maxlend-1 are descriptions and should be fixed
        # maxlend is eos and should be fixed
        flips = sorted(random.sample(range(maxlend+1,maxlen), nflips))
        if debug and b < debug:
            print(b+' ', end='')
        for input_idx in flips:
            if x[b,input_idx] == empty or x[b,input_idx] == eos:
                continue
            # convert from input location to label location
            # the output at maxlend (when input is eos) is feed as input at maxlend+1
            label_idx = input_idx - (maxlend+1)
            prob = probs[b, label_idx]
            w = prob.argmax()
            if w == empty:  # replace accidental empty with oov
                w = oov0
            if debug and b < debug:
                print('%s => %s '%(idx2word[x_out[b,input_idx]],idx2word[w]),)
            x_out[b,input_idx] = w
        if debug and b < debug:
            print()
    return x_out


# In[210]:


def conv_seq_labels(xds, xhs, nflips=None, model=None, debug=False):
    """description and hedlines are converted to padded input vectors. headlines are one-hot to label"""
    batch_size = len(xhs)
    assert len(xds) == batch_size
    x = [vocab_fold(lpadd(xd)+xh) for xd,xh in zip(xds,xhs)]  # the input does not have 2nd eos
    x = sequence.pad_sequences(x, maxlen=maxlen, value=empty, padding='post', truncating='post')
    x = flip_headline(x, nflips=nflips, model=model, debug=debug)
    
    y = np.zeros((batch_size, maxlenh, vocab_size))
    for i, xh in enumerate(xhs):
        xh = vocab_fold(xh) + [eos] + [empty]*maxlenh  # output does have a eos at end
        xh = xh[:maxlenh]
        y[i,:,:] = np_utils.to_categorical(xh, vocab_size)
        
    return x, y


# In[211]:


def gen(Xd, Xh, batch_size=batch_size, nb_batches=None, nflips=None, model=None, debug=False, seed=seed):
    """yield batches. for training use nb_batches=None
    for validation generate deterministic results repeating every nb_batches
    
    while training it is good idea to flip once in a while the values of the headlines from the
    value taken from Xh to value generated by the model.
    """
    c = nb_batches if nb_batches else 0
    while True:
        xds = []
        xhs = []
        if nb_batches and c >= nb_batches:
            c = 0
        new_seed = random.randint(0, sys.maxsize)
        random.seed(c+123456789+seed)
        for b in range(batch_size):
            t = random.randint(0,len(Xd)-1)

            xd = Xd[t]
            s = random.randint(min(maxlend,len(xd)), max(maxlend,len(xd)))
            xds.append(xd[:s])
            
            xh = Xh[t]
            s = random.randint(min(maxlenh,len(xh)), max(maxlenh,len(xh)))
            xhs.append(xh[:s])

        # undo the seeding before we yield inorder not to affect the caller
        c+= 1
        random.seed(new_seed)

        yield conv_seq_labels(xds, xhs, nflips=nflips, model=model, debug=debug)


# In[212]:


r = next(gen(X_train, Y_train, batch_size=batch_size))
r[0].shape, r[1].shape, len(r)


# In[213]:


def test_gen(gen, n=5):
    Xtr,Ytr = next(gen)
    for i in range(n):
        assert Xtr[i,maxlend] == eos
        x = Xtr[i,:maxlend]
        y = Xtr[i,maxlend:]
        yy = Ytr[i,:]
        yy = np.where(yy)[1]
        prt('L',yy)
        prt('H',y)
        if maxlend:
            prt('D',x)


# In[214]:


test_gen(gen(X_train, Y_train, batch_size=batch_size))


# test fliping

# In[215]:


test_gen(gen(X_train, Y_train, nflips=6, model=base_model, debug=False, batch_size=batch_size))


# In[216]:


valgen = gen(X_test, Y_test,nb_batches=3, batch_size=batch_size)


# check that valgen repeats itself after nb_batches

# In[217]:


for i in range(4):
    test_gen(valgen, n=1)


# # Training Starts Here

# In[218]:


history = {}


# In[219]:


traingen = gen(X_train, Y_train, batch_size=batch_size, nflips=nflips, model=base_model)
valgen = gen(X_test, Y_test, nb_batches=nb_val_samples//batch_size, batch_size=batch_size)


# In[ ]:


r = next(traingen)
r[0].shape, r[1].shape, len(r)


# ## Trains the model for a given number of epochs (iterations on a dataset)

# In[ ]:


import time
for iteration in range(501):
    print('Iteration', iteration)
    logging.info('Iteration ' + str(iteration))
    start_time = time.time()
    h = base_model.fit_generator(traingen, steps_per_epoch=nb_train_samples//batch_size,
                        epochs=1, validation_data=valgen, validation_steps=nb_val_samples//batch_size
                           )
    for k,v in h.history.items():
        history[k] = history.get(k,[]) + v
    with open('data/%s.history.pickle'%FN,'wb') as fp:
        pickle.dump(history,fp,-1)
    if(iteration%100==0):
        base_model.save_weights('data/%s_iter%d.hdf5'%(FN,iteration), overwrite=True)
    logging.info('Time taken: ' + str(time.time() - start_time))
    gensamples(batch_size=batch_size)

