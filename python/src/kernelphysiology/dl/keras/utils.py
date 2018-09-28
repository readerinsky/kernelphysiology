'''
Common utility funcions for Keras.
'''

import numpy as np

import math
import keras
from keras import backend as K
from PIL import Image as pil_image


def get_conv2ds(model, topn=math.inf):
    conv2d_inds = []
    for i in range(0, len(model.layers)):
        if type(model.layers[i]) is keras.layers.convolutional.Conv2D:
            conv2d_inds.append(i)
    return conv2d_inds


def set_area_trainable_false(model, num_areas):
    current_area = 1
    for i in range(0, len(model.layers)):
        if type(model.layers[i]) is keras.layers.pooling.MaxPooling2D:
            if num_areas == current_area:
                break
            current_area += 1
        else:
            model.layers[i].trainable = False
    return model


def keras_resize_img(img, target_size, resample=pil_image.NEAREST):
    img = pil_image.fromarray(img).resize(target_size, resample)

    return img


class ResizeGenerator(keras.utils.Sequence):
    'Generates data for Keras'
    def __init__(self, x_data, y_data, num_classes, batch_size=32, target_size=(224, 224), preprocessing_function=None, shuffle=True):
        'Initialisation'
        self.x_data = x_data
        self.y_data = y_data
        self.num_classes = num_classes
        self.batch_size = batch_size
        self.target_size = target_size
        self.preprocessing_function = preprocessing_function
        self.shuffle = shuffle

        if K.image_data_format() == 'channels_last':
            self.out_shape = (*self.target_size, self.x_data.shape[3])
        elif K.image_data_format() == 'channels_first':
            self.out_shape = (self.x_data.shape[1], *self.target_size)

        self.on_epoch_end()

    def __len__(self):
        'Denotes the number of batches per epoch'
        return int(np.floor(self.x_data.shape[0] / self.batch_size))

    def __getitem__(self, index):
        'Generate one batch of data'
        # generate indices of the batch
        current_batch = self.indices[index * self.batch_size:(index + 1) * self.batch_size]

        # generate data
        (x_batch, y_batch) = self.__data_generation(current_batch)

        return (x_batch, y_batch)

    def on_epoch_end(self):
        'Updates indices after each epoch'
        self.indices = np.arange(self.x_data.shape[0])
        if self.shuffle == True:
            np.random.shuffle(self.indices)

    def __data_generation(self, current_batch):
        'Generates data containing batch_size samples'
        # initialisation
        x_batch = np.empty((self.batch_size, *self.out_shape), dtype='float32')
        y_batch = np.empty((self.batch_size, self.num_classes), dtype=int)

        # generate data
        for i, im_id in enumerate(current_batch):
            # store sample
            x_batch[i,] = keras_resize_img(self.x_data[im_id,], self.target_size)

            # store class
            y_batch[i,] = self.y_data[im_id,]

        if self.preprocessing_function:
            x_batch = self.preprocessing_function(x_batch)

        return (x_batch, y_batch)