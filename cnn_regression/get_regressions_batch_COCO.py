import json
import caffe
import numpy as np
from PIL import Image
import os

# Run in GPU
caffe.set_device(0)
caffe.set_mode_gpu()

test_d = {}
test = []
data = json.load(open('../../../datasets/COCO/annotations/test1k.json'))
for id in data:
    if data[id]['image_id'] not in test_d:
        test.append('COCO_val2014_' + str(data[id]['image_id']).zfill(12) + '.jpg')
        test_d[data[id]['image_id']] = 'COCO_val2014_' + str(data[id]['image_id']).zfill(12) + '.jpg'


#Model name
model = 'triplet_softNegativeBatch_m10_sigmoid_frozen_glove_tfidf_SM_iter_500000'

#Output file
output_file_dir = '../../../datasets/COCO/regression_output/' + model
if not os.path.exists(output_file_dir):
    os.makedirs(output_file_dir)
output_file_path = output_file_dir + '/test1k.txt'
output_file = open(output_file_path, "w")

# load net
net = caffe.Net('../googlenet_regression/prototxt/deploy.prototxt', '../../../datasets/SocialMedia/models/saved/'+ model + '.caffemodel', caffe.TEST)

size = 227

# Reshape net
batch_size = 250 #300
net.blobs['data'].reshape(batch_size, 3, size, size)

print 'Computing  ...'

count = 0
i = 0
while i < len(test):
    indices = []
    if i % 100 == 0:
        print i

    # Fill batch
    for x in range(0, batch_size):

        if i > len(test) - 1: break

        # load image
        filename = '../../../datasets/COCO/val2014/' + test[i]
        im = Image.open(filename)
        im_o = im
        im = im.resize((size, size), Image.ANTIALIAS)
        indices.append(test[i])

        # Turn grayscale images to 3 channels
        if (im.size.__len__() == 2):
            im_gray = im
            im = Image.new("RGB", im_gray.size)
            im.paste(im_gray)

        #switch to BGR and substract mean
        in_ = np.array(im, dtype=np.float32)
        in_ = in_[:,:,::-1]
        in_ -= np.array((104, 117, 123))
        in_ = in_.transpose((2,0,1))

        net.blobs['data'].data[x,] = in_

        i += 1

    # run net and take scores
    net.forward()

    # Save results for each batch element
    for x in range(0,len(indices)):
        topic_probs = net.blobs['probs'].data[x]
        topic_probs_str = ''

        for t in topic_probs:
            topic_probs_str = topic_probs_str + ',' + str(t)

        output_file.write(str(indices[x]) + topic_probs_str + '\n')

output_file.close()

print "DONE"
print output_file_path


