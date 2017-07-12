# Load trained LDA model and infer topics for unseen text.
# Make the train/val/test splits for CNN regression training
# It also creates the splits train/val/test randomly

from nltk.tokenize import RegexpTokenizer
from stop_words import get_stop_words
from nltk.stem.porter import PorterStemmer
from gensim import corpora, models
import glob
from random import randint
import string
from joblib import Parallel, delayed
import numpy as np
import gensim
import multiprocessing

# Load data and model
text_data_path = '../../../datasets/SocialMedia/captions_resized_1M/cities_instagram/'
model_path = '../../../datasets/SocialMedia/models/doc2vec/doc2vec_model_instacities1M.model'

# Create output files
gt_path_train = '../../../datasets/SocialMedia/doc2vec_gt/train_InstaCities1M.txt'
gt_path_val = '../../../datasets/SocialMedia/doc2vec_gt/val_InstaCities1M.txt'
gt_path_test = '../../../datasets/SocialMedia/doc2vec_gt/test_InstaCities1M.txt'
train_file = open(gt_path_train, "w")
val_file = open(gt_path_val, "w")
test_file = open(gt_path_test, "w")

cities = ['london','newyork','sydney','losangeles','chicago','melbourne','miami','toronto','singapore','sanfrancisco']

model = gensim.models.Doc2Vec.load(model_path)

size = 400 # vector size
cores = multiprocessing.cpu_count()

num_images_per_city = 20
num_val = num_images_per_city * 0.05
num_test = num_images_per_city *0.15

words2filter = ['rt','http','t','gt','co','s','https','http','tweet','markars_','photo','pictur','picture','say','photo','much','tweet','now','blog']

# create English stop words list
en_stop = get_stop_words('en')

# add own stop words
for w in words2filter:
    en_stop.append(w)

whitelist = string.letters + string.digits + ' '


def infer_LDA(file_name):

    id = file_name.split('/')[-1][:-4]

    with open(file_name, 'r') as file:

        caption = ""
        filtered_caption = ""

        for line in file:
            caption = caption + line

        # Replace hashtags with spaces
        caption = caption.replace('#',' ')

        # Keep only letters and numbers
        for char in caption:
            if char in whitelist:
                filtered_caption += char

        filtered_caption = filtered_caption.lower()
        #Gensim simple_preproces instead tokenizer
        tokens = gensim.utils.simple_preprocess(filtered_caption)
        stopped_tokens = [i for i in tokens if not i in en_stop]

        try:
            embedding = model.infer_vector(stopped_tokens)
        except:
            print "Tokenizer error"
            print stopped_tokens
            return


        # Add zeros to topics without score
        out_string = ''
        for t in range(0,size):
            out_string = out_string + ',' + str(embedding[t])

        return city + '/' + id + out_string


for city in cities:
        print city
        count = 0

        # Single core
        # for file_name in glob.glob(text_data_path + city + "/*.txt"):
        #     s = infer_LDA(file_name)

        parallelizer = Parallel(n_jobs=cores)
        tasks_iterator = (delayed(infer_LDA)(file_name) for file_name in glob.glob(text_data_path + city + "/*.txt"))
        r = parallelizer(tasks_iterator)
        # merging the output of the jobs
        strings = np.vstack(r)

        for s in strings:
        #     # Create splits random
        #     try:
        #         split = randint(0,9)
        #         if split < 8:
        #             train_file.write(s[0] + '\n')
        #         elif split == 8: val_file.write(s[0] + '\n')
        #         else: test_file.write(s[0] + '\n')
        #     except:
        #         print "Error writing to file: "
        #         print s[0]
        #         continue

            # Create splits same number of images per class in each split
            try:
                if count < num_test:
                    test_file.write(s[0] + '\n')
                elif count < num_test + num_val:
                    val_file.write(s[0] + '\n')
                else:
                    train_file.write(s[0] + '\n')
                count += 1
            except:
                print "Error writing to file: "
                print s[0]
                continue


train_file.close()
val_file.close()
test_file.close()

print "Done"
