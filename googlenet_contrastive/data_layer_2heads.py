import caffe

import numpy as np
from PIL import Image
from PIL import ImageOps
import time
import sys
sys.path.append('/usr/src/opencv-3.0.0-compiled/lib/')
import cv2

import random


class twoHeadTripletDataLayer(caffe.Layer):
    """
    Load (input image, label image) pairs from the SBDD extended labeling
    of PASCAL VOC for semantic segmentation
    one-at-a-time while reshaping the net to preserve dimensions.

    Use this to feed data to a fully convolutional network.
    """

    def setup(self, bottom, top):
        """
        Setup data layer according to parameters:

        - sbdd_dir: path to SBDD `dataset` dir
        - split: train / seg11valid
        - mean: tuple of mean values to subtract
        - randomize: load in random order (default: True)
        - seed: seed for randomization (default: None / current time)

        for SBDD semantic segmentation.

        N.B.segv11alid is the set of segval11 that does not intersect with SBDD.
        Find it here: https://gist.github.com/shelhamer/edb330760338892d511e.

        example

        params = dict(sbdd_dir="/path/to/SBDD/dataset",
            mean=(104.00698793, 116.66876762, 122.67891434),
            split="valid")
        """
        # config
        params = eval(self.param_str)
        self.dir = params['dir']
        self.train = params['train']
        self.split = params['split']
        self.mean = np.array(params['mean'])
        self.random = params.get('randomize', True)
        self.seed = params.get('seed', None)
        self.batch_size = params['batch_size']
        self.resize = params['resize']
        self.resize_w = params['resize_w']
        self.resize_h = params['resize_h']
        self.crop_w = params['crop_w']
        self.crop_h = params['crop_h']
        self.crop_margin = params['crop_margin']
        self.mirror = params['mirror']
        self.rotate_prob = params['rotate_prob']
        self.rotate_angle = params['rotate_angle']
        self.HSV_prob = params['HSV_prob']
        self.HSV_jitter = params['HSV_jitter']
        self.color_casting_prob = params['color_casting_prob']
        self.color_casting_jitter = params['color_casting_jitter']
        self.scaling_prob = params['scaling_prob']
        self.scaling_factor = params['scaling_factor']

        self.emotions = ['amusement', 'anger', 'awe', 'contentment', 'disgust', 'excitement', 'fear', 'sadness']

        self.num_classes = params['num_classes']

        print "Initialiting data layer"

        # three tops: data and label_p, label_n
        if len(top) != 4:
            raise Exception("Need to define 4 tops: data, label, regression label and negative regression label.")
        # data layers have no bottoms
        if len(bottom) != 0:
            raise Exception("Do not define a bottom.")

        # load indices for images and labels
        split_f = '{}/{}.txt'.format(self.dir,
                                     self.split)
        num_lines = sum(1 for line in open(split_f))
        #num_lines = 2001

        self.indices = np.empty([num_lines], dtype="S50")
        self.regression_labels = np.zeros((num_lines, self.num_classes))
        self.labels = np.zeros((num_lines,1))



        offset = 2
        print "Reading labels file: " + '{}/{}.txt'.format(self.dir, self.split)
        incorrect_lables = 0
        with open(split_f, 'r') as annsfile:
            for c, i in enumerate(annsfile):
                data = i.split(',')
                # Load path
                self.indices[c] = data[0]
                self.labels[c] = int(data[1])
                # Load regression labels
                for l in range(0, self.num_classes):
                    self.regression_labels[c, l] = float(data[l + offset])
                if sum(self.regression_labels[c, :]) == 0:
                    # print "0's label found, skipping (repeating previous entry)"
                    incorrect_lables += 1
                    self.indices[c] = self.indices[c-1]
                    self.regression_labels[c,:] = self.regression_labels[c-1,:]


                if c % 10000 == 0: print "Read " + str(c) + " / " + str(num_lines) + "  --  0s labels: " + str(incorrect_lables)
                # if c == 2000:
                #      print "Stopping at 3000 labels"
                #      break

        self.indices = [i.split(',', 1)[0] for i in self.indices]

        # make eval deterministic
        # if 'train' not in self.split and 'trainTrump' not in self.split:
        #     self.random = False

        self.idx = np.arange(self.batch_size)

        # randomization: seed and pick
        if self.random:
            print "Randomizing image order"
            random.seed(self.seed)
            for x in range(0, self.batch_size):
                self.idx[x] = random.randint(0, len(self.indices) - 1)

        else:
            for x in range(0, self.batch_size):
                self.idx[x] = x


        # reshape tops to fit
        # === reshape tops ===
        # since we use a fixed input image size, we can shape the data layer
        # once. Else, we'd have to do it in the reshape call.
        top[0].reshape(self.batch_size, 3, params['crop_w'], params['crop_h'])
        top[1].reshape(self.batch_size, self.num_classes)
        top[2].reshape(self.batch_size, self.num_classes)
        top[3].reshape(self.batch_size, 1)


    def reshape(self, bottom, top):
        # load image + label image pair
        self.data = np.zeros((self.batch_size, 3, self.crop_w, self.crop_h))
        self.label_regression = np.zeros((self.batch_size, self.num_classes))
        self.label_regression_negative = np.zeros((self.batch_size, self.num_classes))
        self.label = np.zeros((self.batch_size, 1))

        for x in range(0, self.batch_size):
            # try:
            # except:
            #     print("Image could not be loaded. Using 0s")
            self.label_regression[x,] = self.regression_labels[self.idx[x],]
            self.label[x,] = int(self.labels[self.idx[x]])
            self.data[x,] = self.load_image(self.indices[self.idx[x]], self.label[x,])

        # SOFT NEGATIVE SELECTION
        # Select a random element from the half that have more w2v distance than the mean w2v distance in the batch.
        for x in range(0, self.batch_size):
            c=0
            while(True):
                c+=1
                neg_idx = random.choice(self.idx)
                if int(self.labels[neg_idx]) is not int(self.label[x]) or c == 100:
                    break
                c+=1

            self.label_regression_negative[x,] = self.regression_labels[neg_idx,]

    def forward(self, bottom, top):
        # assign output
        top[0].data[...] = self.data
        top[1].data[...] = self.label_regression
        top[2].data[...] = self.label_regression_negative
        top[3].data[...] = self.label

        self.idx = np.arange(self.batch_size)

        # pick next input
        if self.random:
            for x in range(0, self.batch_size):
                self.idx[x] = random.randint(0, len(self.indices) - 1)

        else:
            for x in range(0, self.batch_size):
                self.idx[x] = self.idx[x] + self.batch_size

            if self.idx[self.batch_size - 1] == len(self.indices):
                for x in range(0, self.batch_size):
                    self.idx[x] = x

    def backward(self, top, propagate_down, bottom):
        pass

    def load_image(self, idx, label):
        """
        Load input image and preprocess for Caffe:
        - cast to float
        - switch channels RGB -> BGR
        - subtract mean
        - transpose to channel x height x width order
        """
        if self.dir == '../../../datasets/SocialMedia':
            im = Image.open('{}/{}/{}'.format(self.dir, 'img_resized_1M/cities_instagram', idx + '.jpg'))

        elif self.split == '/info/val_filelist':
            im = Image.open('{}/{}/{}'.format(self.dir, 'val_images_256', idx))
        elif self.dir == '../../../datasets/Wikipedia':
            im = Image.open('{}/{}/{}'.format(self.dir, 'images', idx + '.jpg'))
        elif self.dir == '../../../datasets/MIRFLICKR25K':
            im = Image.open('{}/{}/{}'.format(self.dir, 'img', 'im' + idx + '.jpg'))
        elif self.dir == '../../../ssd2/InstaBarcelona':
            im = Image.open('{}/{}/{}'.format(self.dir, 'img_resized',idx + '.jpg'))
        elif self.dir == '../../../datasets/EmotionDataset':
            im = Image.open('{}/{}/{}'.format(self.dir, 'img/' + str(self.emotions[int(label)]), idx + '.jpg'))
        elif self.dir == '../../../hd/datasets/instaEmotions':
            im = Image.open('{}/{}/{}'.format(self.dir, 'img_resized', idx + '.jpg'))
        else:
            im = Image.open('{}/{}'.format(self.dir, idx))

        if self.resize:
            if im.size[0] != self.resize_w or im.size[1] != self.resize_h:
                im = im.resize((self.resize_w, self.resize_h), Image.ANTIALIAS)

        #if self.train:  # Data Aumentation

        if (self.scaling_prob is not 0):
            im = self.rescale_image(im)

        if (self.rotate_prob is not 0):
            im = self.rotate_image(im)

        if self.crop_h is not im.size[0] or self.crop_h is not im.size[1]:
            im = self.random_crop(im)

        if (self.mirror and random.randint(0, 1) == 1):
            im = self.mirror_image(im)

        if (self.HSV_prob is not 0):
            im = self.saturation_value_jitter_image(im)

        if (self.color_casting_prob is not 0):
            im = self.color_casting(im)

        # end = time.time()
        # print "Time data aumentation: " + str((end - start))
        in_ = np.array(im, dtype=np.float32)

        if (in_.shape.__len__() < 3 or in_.shape[2] > 3):
            im_gray = im
            im = Image.new("RGB", im_gray.size)
            im.paste(im_gray)
            in_ = np.array(im, dtype=np.float32)

        in_ = in_[:, :, ::-1]
        in_ -= self.mean
        in_ = in_.transpose((2, 0, 1))
        return in_

    # DATA AUMENTATION

    def random_crop(self, im):
        # Crops a random region of the image that will be used for training. Margin won't be included in crop.
        width, height = im.size
        margin = self.crop_margin
        if width or height < self.crop_h:
            im = im.resize((self.crop_h+1, self.crop_h+1), Image.ANTIALIAS)
            width, height = im.size
        left = random.randint(margin, width - self.crop_w - 1 - margin)
        top = random.randint(margin, height - self.crop_h - 1 - margin)
        im = im.crop((left, top, left + self.crop_w, top + self.crop_h))
        return im

    def mirror_image(self, im):
        return ImageOps.mirror(im)

    def rotate_image(self, im):
        if (random.random() > self.rotate_prob):
            return im
        return im.rotate(random.randint(-self.rotate_angle, self.rotate_angle))

    def saturation_value_jitter_image(self, im):
        if (random.random() > self.HSV_prob):
            return im
        # im = im.convert('HSV')
        data = np.array(im)  # "data" is a height x width x 3 numpy array
        if len(data.shape) < 3: return im
        hsv_data = cv2.cvtColor(data, cv2.COLOR_RGB2HSV)
        hsv_data[:, :, 1] = hsv_data[:, :, 1] * random.uniform(1 - self.HSV_jitter, 1 + self.HSV_jitter)
        hsv_data[:, :, 2] = hsv_data[:, :, 2] * random.uniform(1 - self.HSV_jitter, 1 + self.HSV_jitter)
        data = cv2.cvtColor(hsv_data, cv2.COLOR_HSV2RGB)
        im = Image.fromarray(data, 'RGB')
        # im = im.convert('RGB')
        return im

    def rescale_image(self, im):
        if (random.random() > self.scaling_prob):
            return im
        width, height = im.size
        im = im.resize((int(width * self.scaling_factor), int(height * self.scaling_factor)), Image.ANTIALIAS)
        return im

    def color_casting(self, im):
        if (random.random() > self.color_casting_prob):
            return im
        data = np.array(im)  # "data" is a height x width x 3 numpy array
        if len(data.shape) < 3: return im
        ch = random.randint(0, 2)
        jitter = random.randint(0, self.color_casting_jitter)
        data[:, :, ch] = data[:, :, ch] + jitter
        im = Image.fromarray(data, 'RGB')
        return im