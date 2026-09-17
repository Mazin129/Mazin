# Machine Learning

Machine learning is a field of artificial intelligence where a computer learns patterns from data instead of being explicitly programmed with rules.
Artificial intelligence is the broader effort to make computers perform tasks that normally require human intelligence, such as reasoning, perception, and language.
A model is the mathematical function a machine learning system learns from data and then uses to make predictions on new inputs.
Training is the process of adjusting a model's parameters so its predictions match the known answers in the training data.
Inference is the process of using a trained model to make a prediction on a new, unseen input.
A dataset is the collection of examples a model learns from, usually split into training, validation, and test sets.
A feature is a measurable input variable that a model uses to make a prediction, such as the pixels of an image or the words in a sentence.
A label is the correct answer attached to a training example that a supervised model learns to predict.
A parameter is a value inside a model, such as a weight, that is adjusted during training to reduce error.
A hyperparameter is a setting chosen before training, such as the learning rate or the number of layers, that controls how the model learns.

## Kinds of learning

Supervised learning trains a model on labeled examples so it learns to map inputs to known outputs.
Unsupervised learning finds structure in data that has no labels, such as grouping similar items together.
Reinforcement learning trains an agent to take actions in an environment to maximize a reward signal over time.
Self-supervised learning creates its own labels from the data itself, which is how large language models learn to predict the next word.
Classification is a supervised task where the model predicts which category an input belongs to, such as spam or not spam.
Regression is a supervised task where the model predicts a continuous number, such as the price of a house.
Clustering is an unsupervised task where the model groups similar examples together without being told the categories.

## Training and error

A loss function measures how wrong a model's predictions are, giving a single number that training tries to make smaller.
Gradient descent is the algorithm that reduces the loss by repeatedly nudging the parameters in the direction that lowers error the most.
The learning rate controls how big each gradient descent step is; too high overshoots and too low learns slowly.
Backpropagation is the algorithm that computes how much each weight in a neural network contributed to the error, so gradient descent can update it.
An epoch is one full pass of the training algorithm over the entire training dataset.
A batch is the small group of examples the model processes at once before updating its weights.
Overfitting happens when a model memorizes the training data and fails to generalize to new data.
Underfitting happens when a model is too simple to capture the pattern in the data, so it performs poorly even on the training set.
Regularization is any technique, such as dropout or weight decay, that discourages overfitting by keeping the model simpler.
The bias-variance tradeoff is the balance between a model too simple to fit the data and a model so flexible it fits the noise.
Cross-validation checks how well a model generalizes by training and testing it on several different splits of the data.

## Neural networks and deep learning

A neural network is a model made of layers of connected units, loosely inspired by neurons, that learns complex patterns from data.
Deep learning is machine learning with neural networks that have many layers, which lets them learn rich features directly from raw data.
A neuron in a neural network takes several inputs, multiplies each by a weight, sums them, and passes the result through an activation function.
An activation function adds non-linearity to a neural network so it can learn patterns more complex than a straight line.
A weight is a learned number that sets how strongly one unit's output influences the next unit.
A convolutional neural network is a network that uses sliding filters to detect patterns in images, and is the backbone of computer vision.
A recurrent neural network processes sequences one step at a time while carrying a memory of what came before.

## Language models and transformers

A transformer is a neural network architecture that uses attention to weigh the importance of every word against every other word in a sequence.
Attention is the mechanism that lets a model focus on the most relevant parts of the input when producing each part of the output.
A large language model is a transformer trained on huge amounts of text to predict the next token, which lets it generate and understand language.
A token is a small chunk of text, such as a word or piece of a word, that a language model reads and predicts one at a time.
An embedding is a list of numbers that represents the meaning of a word or item, so that similar things sit close together in that space.
Fine-tuning is further training of a pretrained model on a smaller, specific dataset to adapt it to a particular task.
A prompt is the input text given to a language model to guide what it generates.
Retrieval-augmented generation improves a language model's answers by first fetching relevant documents and giving them to the model as context.
A hallucination is when a language model generates text that sounds confident but is factually wrong or unsupported.

## Evaluation

Accuracy is the fraction of predictions a model got correct, and it can mislead when the classes are imbalanced.
Precision is the fraction of the model's positive predictions that were actually correct.
Recall is the fraction of the actual positive cases that the model successfully found.
The F1 score is the harmonic mean of precision and recall, balancing the two into a single number.
A confusion matrix is a table that shows how many predictions fell into each combination of predicted and actual class.
Generalization is a model's ability to perform well on new data it did not see during training, which is the real goal of learning.
