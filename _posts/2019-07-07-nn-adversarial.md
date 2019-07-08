---
title: I tricked m3.euagendas.org, the Twitter analysis website, with adversarial inputs
categories: twitter, m3inference, foolbox, adversarial, nn
permalink: /nn-adversarial/
image: /assets/blog/nn-adversarial/cover.png
---

I tricked [m3.euagendas.org](http://m3.euagendas.org), the viral third-party Twitter account analysis website, into thinking I'm 40 years old: it only took 78 lines of code to generates an adversarial input against its neural network, using Foolbox, PyTorch, and Python.

# Introduction

![Screenshot of two m3.euagendas.org results for two Twitter accounts, with "Age: >=40" circled on the right one](/assets/blog/nn-adversarial/cover.png)

These Twitter accounts ([@1Zhuowei](https://twitter.com/1Zhuowei), [@2Zhuowei](https://twitter.com/2Zhuowei)) have the same avatar, same bio, and same display name, yet [**m3inference** (m3.euagendas.org)](http://m3.euagendas.org) classifies the first one as "19-29 years old", but the second as ">= 40 years old".

How? [Adversarial inputs](https://en.wikipedia.org/wiki/Adversarial_machine_learning).

I tricked m3inference by modifying the avatar of the account on the right. A human can't tell the difference, but to m3inference's neural network, the image appears as a >=40 years old person.

# What's m3inference?

If you've been on Twitter last week, you've seen [**m3inference** (m3.euagendas.org)](http://m3.euagendas.org).

As the [authors' paper](https://arxiv.org/abs/1905.05961) explains, m3inference is a tool, created by [university researchers](http://www.ox.ac.uk/news/2019-05-16-new-machine-learning-algorithm-can-predict-age-and-gender-just-your-twitter-profile), that attempts to guess:

- your age
- gender
- whether you're a corporate account (Brand&trade;)

based only on four pieces of info from your public Twitter profile:

- username
- display name
- bio
- and avatar image.

Here's what it outputs for a corporate account: [@AskVoco](https://twitter.com/AskVoco), a voice app for bringing personalized news to your Amazon Alexa and Google Home speakers, made by a group of my friends. (an account you should TOTALLY FOLLOW, BTW\</subtle-plug>)

![screenshot of m3inference on @AskVoco](/assets/blog/nn-adversarial/askvoco.png)

<br><br>

Here's what it outputs for a person: [@zijianwang30](https://twitter.com/zijianwang30), one of the authors who built m3inference.

![screenshot of m3inference on @zijianwang30](/assets/blog/nn-adversarial/zijianwang30.png)

<br><br>

Since m3infererence was released, many other Twitter users have tried this on their own accounts - a [search for "m3.euagendas.org" on Twitter](https://twitter.com/search?f=tweets&vertical=default&q=http%3A%2F%2Fm3.euagendas.org&src=typd) returns a large number of results.

# M3inference's shortcomings

With m3infererence's popularity came concerns from other Twitter users about [privacy](https://twitter.com/ixtility/status/1146848693515116544), [the ethics](https://twitter.com/farbandish/status/1146827191612772353) of [automatic gender inference](https://ironholds.org/resources/papers/agr_paper.pdf), and the [potential applications for the technology](https://twitter.com/thursdaysrain/status/1146862357735514112).

The most common complaint, however, is that the detector simply isn't accurate enough to be relied upon.

For example, it classifies [me](https://twitter.com/zhuowei) as a corporate account!

![screenshot of m3inference on @zhuowei, saying that I'm a corporate account](/assets/blog/nn-adversarial/zhuowei_is_a_brand.png)

I created an alternate account, [@1Zhuowei](https://twitter.com/zhuowei), and found that the algorithm's age prediction is so fragile, it makes completely different predictions when there's a "1" in the username:

![screenshot of m3inference on @1zhuowei, with @zhuowei's age results besides: it's a lot less confident about my age group now](/assets/blog/nn-adversarial/1zhuowei_age.png)

[@0xabad1dea suggested](m3inference) that m3inference might associate QR codes strongly with brands.

Surely it can't be that simple: there's no way just swapping the avatar would change its prediction of my account from Brand&trade; to real person.

![screenshot of m3inference on @1zhuowei, with a new avatar (rocket taking off): "Non-Org" with 99% confidence](/assets/blog/nn-adversarial/new_avatar.png)

It actually worked?!

I'm now recognized as "Non-Org" with 99.94% confidence, up from 26%, just by swapping my avatar with [a photo of a rocket launch](https://images.nasa.gov/details-KSC-20190702-PH_KLS01_0063.html).

This doesn't make me feel confident about m3inference's reliability: I managed to sway its results with nothing more than a picture.

What if I want to change my results without changing my entire avatar? For that, I'll need to understand how m3inference works.

# How m3inference works

m3infererence's authors released the [full source code of their app](https://github.com/euagendas/m3inference), with a script that automatically downloads their pre-trained model. (This is **super awesome**, and I wish more academic researchers would do this!)

As detailed in the authors' paper, m3infererence works by retrieving a user's Twitter username, display name, bio, and avatar image, then passing it into a neural network with the following structure:

![screenshot of neural network from paper](/assets/blog/nn-adversarial/network.png){: width="320"}

_The neural network structure: image taken from the m3infererence paper_

It uses DenseNet to process the avatar and three LSTMs to process the text. It then adds two more neural network layers to combine the predictions from all four networks into one.

Looking at the inputs, I decided to focus on the avatar: while there's not much research on subtlely changing text to trick a neural network, there's plenty of research on how to subtlely modify an image to cause a neural network to make mistakes.

# What are adversarial inputs?

To trick neural networks, I use a technique called [Adversarial machine learning](https://en.wikipedia.org/wiki/Adversarial_machine_learning), which has successfully fooled [image recognition](https://ai.googleblog.com/2018/09/introducing-unrestricted-adversarial.html), [self driving cars](https://spectrum.ieee.org/cars-that-think/transportation/sensors/slight-street-sign-modifications-can-fool-machine-learning-algorithms), and even [a smartphone's dictation feature](https://nicholas.carlini.com/code/audio_adversarial_examples/).

To create an adversarial input, we make small changes to an original input (such as an image). These changes are imperceptable to a human, but causes the neural network to make dramatic errors. This is done with an elegant method.

Usually, in machine learning, we train neural networks to output a specific answer, given an image.

To generate an adversarial input, we flip this around: we train **the image** to output a specific answer, given **a neural network**.

The beauty of this technique is that we can use the exact same methods that we're already using to train neural networks to generate these images, just by swapping the inputs. We can even take advantage of existing optimizations made for neural networks, such as weight normalization, to make sure our changes are small and not likely to be noticed by humans.

There's tons of [guides](https://blog.ycombinator.com/how-adversarial-attacks-work/) on [how](https://lisaong.github.io/mldds-courseware/03_TextImage/adversarial.slides.html) to generate adversarial images yourself (I even saw a live demo in our machine learning class!), but nowadays, there's libraries that does all the work for you.

# Generating an adversarial input with Foolbox

Thanks to the [Foolbox](https://github.com/bethgelab/foolbox) library, it only took me [78 lines of code](https://github.com/zhuowei/m3exploration/blob/master/fakeme.py) to trick m3inference's Twitter classifier.

Foolbox is a prebuilt tool for generating adversarial inputs for any neural network, using a variety of built-in techniques. All I had to do was pass in m3inference's pretrained PyTorch model into it.

To use Foolbox against the m3inference tool, I first fetch the Twitter account info and original avatar, using m3inference itself.

```
username = "2zhuowei"

# download user data with m3inference if needed

m3cachedir = "cachedir"

username_file = m3cachedir + "/" + username + ".json"
if not os.path.exists(username_file):
    print("Generating initial inference with m3inference")
    m3twitter = m3inference.M3Twitter(cache_dir=m3cachedir, model_dir="./")
    m3twitter.infer_screen_name(username)

with open(username_file, "r") as infile:
    user_data = json.load(infile)
```

Next, I load m3inference's Twitter model into Foolbox.

Foolbox offers builtin support for PyTorch models, as used by m3inference. However, Foolbox expects a model to take a single image as input. m3inference's neural network requires not only an image, but also display name, username, and bio. It also expects them in a batch format.

Thus, I made a `M3ModifiedModel` class, which:

- adds the original display name, username, and bio to the candidate input image
- converts everything to a batch format with PyTorch's DataLoader
- then passes it to the m3inference model.

```
# Load the image

dataset = m3inference.dataset.M3InferenceDataset([user_data["input"]], use_img=True)
dataset_tensors = list(dataset[0])
start_image = dataset_tensors[-1].numpy()

class M3ModifiedModel(m3inference.full_model.M3InferenceModel):
    def forward(self, data, label=None):
        newdata = dataset_tensors[:-1] + [data[0].float()]
        newdataloader = torch.utils.data.DataLoader(newdata, batch_size=1)
        output = super().forward(newdataloader, label)
        print(output)
        return output[1] # <18, 19-29, 30-39, >=40

m3model = M3ModifiedModel(device="cpu")
m3model.eval()
m3model.load_state_dict(torch.load("./full_model.mdl", map_location="cpu"))
```

Now it's time to create the Foolbox representation for our PyTorch neural network.

I tell Foolbox that the m3inference Twitter model has 4 age categories, and that it uses an image format where each pixel has value from 0-1.

```
num_classes = 4 # 4 age groups
fmodel = foolbox.models.PyTorchModel(m3model, bounds=(0, 1), num_classes=num_classes)
```

Before I can generate an adversarial input, I need to know the original age group that m3inference currently outputs.

```
forward_result = fmodel.forward_one(start_image)
cur_max = -1
cur_class = -1
for i in range(len(forward_result)):
    if forward_result[i] >= cur_max:
        cur_max = forward_result[i]
        cur_class = i
print(cur_class)
```

There's one extra wrinkle: Foolbox passes the neural network's output through the softmax function. However, m3inference's network includes its own softmax layer, so I needed to disable Foolbox's layer. This is done with the `TargetClassProbabilityPostSoftmax` wrapper.

```
class TargetClassProbabilityPostSoftmax(foolbox.criteria.TargetClassProbability):
    # our nn already includes a softmax, so the target class doesn't need to do it
    def is_adversarial(self, predictions, label):
        return predictions[self.target_class()] > self.p
```

Once that's done, I tell Foolbox that I want to make the neural network classify my Twitter avatar as ">=40 years old", with greater than 90% probability.

I had to specify such a high probability, because Twitter uses JPEG to compress avatars: this erases a large portion - but not all - of the changes made to the adversarial image. Hopefully, by specifying a super high probability, enough changes would survive and affect the neural network.

```
target_class = 3 # >=40
criterion = TargetClassProbabilityPostSoftmax(target_class, p=0.9)
```

Finally, I run Foolbox on the neural network and avatar.

I originally tried [Fast Gradient Step Method](https://blog.ycombinator.com/how-adversarial-attacks-work/), which uses the same gradient descent optimization that is used to train neural networks. However, this didn't seem to work on my avatar (it only got to 30% likelyhood), so I tried [LBFGS](https://en.wikipedia.org/wiki/Limited-memory_BFGS), another optimization method using Newton's Method, suggested by [Foolbox's tutorial](https://foolbox.readthedocs.io/en/latest/user/tutorial.html).

```
attack = foolbox.attacks.LBFGSAttack(fmodel, criterion)
adversarial = attack(start_image, cur_class, maxiter=20)
```

And that's it! I get an image in `adversarial`; all I had to do was upload it as my Twitter avatar to get the results shown above.

# Results

Original vs Adversarial image:

![Original](/assets/blog/nn-adversarial/2zhuowei_224x224.png) ![Result - looks the same](/assets/blog/nn-adversarial/adversarial_output.png)

My reaction:

![Pam from "The Office" saying "They're the same picture"](/assets/blog/nn-adversarial/same_picture.jpg){: width="320"}

_(Pam from the TV show "The Office" saying "They're the same picture".)_

If I look really hard, I can [convince myself that I see](https://en.wikipedia.org/wiki/Pareidolia) a little [silhouetto](https://www.youtube.com/watch?v=fJ9rUzIMcZQ) of a man in the exhaust fumes on the right of the modified picture - but it's so subtle, you won't notice unless I told you.

Here's the differences between the photos, exaggerated, and my attempt to outline the face-like area:

![the plume shows a bunch of wavy changes, resembling hair, or wrinkles](/assets/blog/nn-adversarial/adversarial_noise_enhance.png)
![a face drawn in the plume](/assets/blog/nn-adversarial/adversarial_silhouette.png)

There's no way a human could notice those changes without enhancement - but the computer is absolutely fooled.

Uploading the new profile picture dramatically changes the age detected by the neural network.

With the original picture, m3inference says my age is 19-29 with 47.83% accuracy:

![m3inference result on @2Zhuowei: Age: 19-29](/assets/blog/nn-adversarial/before_2zhuowei.png)

With the modified picture, m3inference says my age is greater than 40 with 64.49% accuracy:

![m3inference result on @2Zhuowei: Age: >=40](/assets/blog/nn-adversarial/after_2zhuowei.png)

The whole process took me only one day to research and code, and just 20 minutes to generate the image itself, running on a laptop with no GPU.

# Conclusion

Adversarial images are surprisingly easy to generate, yet preplexingly hard to defend against:

First, just modifying how you train neural networks [helps, but doesn't prevent the issue](https://openai.com/blog/adversarial-example-research/).

Next, you might've noticed that I have full access to the trained model. Restricting access to the model would slow the generation of adversarial inputs, but won't prevent it. Black-box approaches exist, where I:

- [train my own](https://github.com/tensorflow/cleverhans#tutorials-cleverhans_tutorials-directory) similar neural network
- generate adversarial inputs on my own network
- and use those on the original network.

Finally, transforming the image before providing it as input works well for rejecting adversarial inputs: just the JPEG compression used by Twitter lowered m3inference's certainty from 90% to 64.49%. However, as more transforms are added, the neural network [becomes worse](https://devblogs.nvidia.com/combating-adversarial-attacks-barrage-random-transforms/
) at recognizing actual valid input.

As a developer, I conducted this experiment because I believe it's important to understand how a technology can fail. Only then can I fully evaluate a technology's impact, and mitigate potential weaknesses.

# What I learned

- Generating adversarial inputs for neural networks
- How easy it is to fool a neural network
- Before deploying new technology, first find out how it can fail, so you can find ways to mitigate the impact