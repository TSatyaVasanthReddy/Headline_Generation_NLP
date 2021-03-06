# Headline_Generation_NLP
### Refer to the Report.pdf for detailed description
## 1. Problem Formation
Headline generation is within the category of the text summarization. In this project, we would like to modify the current way of headline generation and automatically generate headlines from the text of news articles. Since headlines are terse and convey the most important theme of the input text, it won’t be appropriate to just select a subset of actual sentences from the original text as a summary. Instead, it should be generated by building the semantic representation of the text to create a summary. 

The model of news headline generation we are trying to improve in this project is the one proposed by Konstantin Lopyrev [1], which adopts an end-to-end encoder-decoder framework as well as utilizes attention mechanism. The encoder and the decoder are each a recurrent neural network [2]. The encoder encodes a source article into a sequence of latent vectors, and the decoder outputs a summary word by word based on the latent vectors. The attention mechanism allows the decoder to attend to different parts of the source. 

## 2. Project Plans
We plan to use ELMo embedding [3] instead of GloVe embedding [4] to encode the input text. ELMo naturally captures the contextual information by training a large-scale bidierctional language model and is proved to have better performance on many supervised NLP tasks. In this project, we will use the pretrained model which can be obtained [here](https://github.com/allenai/allennlp/blob/master/tutorials/how_to/elmo.md)

We also plan to implement a bidirectional RNN to preserve information from both directions. The original RNN model only takes into consideration the current and the previous words to decide values to assign the neurons, while using bidirectional RNN considers also the words that follow. 

## 3. Dataset and Evaluation
The ideal dataset for this project would be the English Gigaword. It was used by Lopyrev, however we may need to deal with copyright issues first. The alternative dataset we use is All the news dataset [5] which contains 143 thousands articles from 15 American publications. 

We will evaluate generated news headlines with BLEU [6]. In general, BLEU measures how much the words in the machine-generated headlines appeared in the human reference headlines in terms of different n-gram.

## Reference
[1] Lopyrev, Konstantin. "Generating news headlines with recurrent neural networks." arXiv preprint arXiv:1512.01712(2015).
[2] Ilya Sutskever, Oriol Vinyals, and Quoc V. Le. Sequence to sequence learning with neural networks. CoRR, abs/1409.3215, 2014.
[3] Peters M E, Neumann M, Iyyer M, et al. Deep contextualized word representations[J]. arXiv preprint arXiv:1802.05365, 2018.
[4] Pennington J, Socher R, Manning C. Glove: Global vectors for word representation[C]. Proceedings of the 2014 conference on empirical methods in natural language processing (EMNLP). 2014: 1532-1543.
[5] All the news dataset. Kaggle. [link](https://www.kaggle.com/snapcrack/all-the-news/data)
[6] Papineni, K.; Roukos, S.; Ward, T.; Zhu, W. J. BLEU: a method for automatic evaluation of machine translation. ACL-2002: 40th Annual Meeting of the Association for Computational Linguistics. Pp. 311-318.
