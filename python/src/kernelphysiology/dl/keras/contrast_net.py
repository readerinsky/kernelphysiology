'''
Utilities common to CIFAR10 and CIFAR100 datasets.
'''


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

import numpy as np
import keras
from keras.preprocessing.image import ImageDataGenerator
from keras.engine.training import Model
from keras.layers import Add, Conv2D, MaxPooling2D, Dropout, Flatten, Dense, BatchNormalization, Activation, Input
from keras import regularizers

from kernelphysiology.filterfactory.gaussian import gauss


def preprocess_input(img):
    img = img.astype('float32')
    img = (img - 127.5) / 127.5
    return img


def train_model(confs):
    x_train = confs.x_train
    y_train = confs.y_train
    x_test = confs.x_test
    y_test = confs.y_test
    callbacks = confs.callbacks
    batch_size = confs.batch_size
    epochs = confs.epochs

    if not confs.data_augmentation:
        print('Not using data augmentation.')
        if not confs.parallel_model == None:
            batch_size *= confs.multi_gpus
            confs.parallel_model.fit(x_train, y_train, batch_size=batch_size, epochs=epochs, validation_data=(x_test, y_test), shuffle=True, callbacks=callbacks)
        else:
            confs.model.fit(x_train, y_train, batch_size=batch_size, epochs=epochs, validation_data=(x_test, y_test), shuffle=True, callbacks=callbacks)
    else:
        print('Using real-time data augmentation.')
        # This will do preprocessing and realtime data augmentation:
        datagen = ImageDataGenerator(
                featurewise_center=False,  # set input mean to 0 over the dataset
                samplewise_center=False,  # set each sample mean to 0
                featurewise_std_normalization=False,  # divide inputs by std of the dataset
                samplewise_std_normalization=False,  # divide each input by its std
                zca_whitening=False,  # apply ZCA whitening
                rotation_range=0,  # randomly rotate images in the range (degrees, 0 to 180)
                width_shift_range=0.1,  # randomly shift images horizontally (fraction of total width)
                height_shift_range=0.1,  # randomly shift images vertically (fraction of total height)
                horizontal_flip=True,  # randomly flip images
                vertical_flip=False)  # randomly flip images

        # Compute quantities required for feature-wise normalisation
        # (std, mean, and principal components if ZCA whitening is applied).
        datagen.fit(x_train)

        # Fit the model on the batches generated by datagen.flow().
        if not confs.parallel_model == None:
            batch_size *= confs.multi_gpus
            confs.parallel_model.fit_generator(datagen.flow(x_train, y_train, batch_size=batch_size),
                                               epochs=epochs,
                                               validation_data=(x_test, y_test),
                                               workers=4)
        else:
            confs.model.fit_generator(datagen.flow(x_train, y_train, batch_size=batch_size),
                                      epochs=epochs,
                                      validation_data=(x_test, y_test),
                                      workers=4)

    # Save model and weights
    if not os.path.isdir(confs.save_dir):
        os.makedirs(confs.save_dir)
    model_name = confs.model_name + '.h5'
    model_path = os.path.join(confs.save_dir, model_name)
    confs.model.save(model_path)
    print('Saved trained model at %s ' % model_path)

    return confs


def create_dog_layer(confs, nkernels, kernel_size, nchannels=3):
    dogs = np.zeros((kernel_size, kernel_size, nchannels, nkernels))
    for i in range(0, nkernels):
        for j in range(0, nchannels):
            sigma1 = np.random.uniform(0, 1)
            g1 = gauss.gkern(kernel_size, sigma1)
            sigma2 = np.random.uniform(0, 1)
            g2 = gauss.gkern(kernel_size, sigma2)
            dg = -g1 + g2
            dogs[:, :, j, i] = dg
    return dogs


def build_classifier_model(confs):
    n_conv_blocks = 5  # number of convolution blocks to have in our model.
    n_filters_dog = 64
    n_filters = 64  # number of filters to use in the first convolution block.
    l2_reg = regularizers.l2(2e-4)  # weight to use for L2 weight decay. 
    activation = 'elu'  # the activation function to use after each linear operation.

    area1_nlayers = confs.area1_nlayers
    area1_batchnormalise = confs.area1_batchnormalise
    area1_activation = confs.area1_activation

    x = input_1 = Input(shape=confs.x_train.shape[1:])

    if confs.add_dog:
        x = Conv2D(filters=n_filters_dog, kernel_size=(3, 3), padding='same', name='dog')(x)

    # each convolution block consists of two sub-blocks of Conv->Batch-Normalization->Activation,
    # followed by a Max-Pooling and a Dropout layer.
    for i in range(n_conv_blocks):
        if i == 0:
            if area1_nlayers == 1:
                x = Conv2D(filters=n_filters, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                if area1_batchnormalise:
                    x = BatchNormalization()(x)
                if area1_activation:
                    x = Activation(activation=activation)(x)
            else:
                x = Conv2D(filters=n_filters, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                if area1_batchnormalise:
                    x = BatchNormalization()(x)
                if area1_activation:
                    x = Activation(activation=activation)(x)

                if area1_nlayers == 2:
                    x = Conv2D(filters=44, kernel_size=(3, 3), dilation_rate=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                    if area1_batchnormalise:
                        x = BatchNormalization()(x)
                    if area1_activation:
                        x = Activation(activation=activation)(x)

                elif area1_nlayers == 3:
                    x = Conv2D(filters=37, kernel_size=(3, 3), dilation_rate=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                    if area1_batchnormalise:
                        x = BatchNormalization()(x)
                    if area1_activation:
                        x = Activation(activation=activation)(x)

                    x = Conv2D(filters=37, kernel_size=(3, 3), dilation_rate=(9, 9), padding='same', kernel_regularizer=l2_reg)(x)
                    if area1_batchnormalise:
                        x = BatchNormalization()(x)
                    if area1_activation:
                        x = Activation(activation=activation)(x)

                elif area1_nlayers == 4:
                    x = Conv2D(filters=27, kernel_size=(3, 3), dilation_rate=(1, 1), padding='same', kernel_regularizer=l2_reg)(x)
                    if area1_batchnormalise:
                        x = BatchNormalization()(x)
                    if area1_activation:
                        x = Activation(activation=activation)(x)

                    x = Conv2D(filters=64, kernel_size=(3, 3), dilation_rate=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                    if area1_batchnormalise:
                        x = BatchNormalization()(x)
                    if area1_activation:
                        x = Activation(activation=activation)(x)

                    x = Conv2D(filters=27, kernel_size=(3, 3), dilation_rate=(7, 7), padding='same', kernel_regularizer=l2_reg)(x)
                    if area1_batchnormalise:
                        x = BatchNormalization()(x)
                    if area1_activation:
                        x = Activation(activation=activation)(x)

            if confs.area1_reduction:
                x = Conv2D(filters=n_filters, kernel_size=(1, 1), padding='same', kernel_regularizer=l2_reg)(x)
        else:
            shortcut = Conv2D(filters=n_filters, kernel_size=(1, 1), padding='same', kernel_regularizer=l2_reg)(x)
            x = Conv2D(filters=n_filters, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
            x = BatchNormalization()(x)
            x = Activation(activation=activation)(x)

            x = Conv2D(filters=n_filters, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
            x = Add()([shortcut, x])
            x = BatchNormalization()(x)
            x = Activation(activation=activation)(x)

        x = MaxPooling2D(pool_size=(2, 2))(x)
        x = Dropout(rate=0.25)(x)

        n_filters *= 2

    # finally, we flatten the output of the last convolution block, and add two Fully-Connected layers.
    x = Flatten()(x)
    x = Dense(units=512, kernel_regularizer=l2_reg)(x)
    x = BatchNormalization()(x)
    x = Activation(activation=activation)(x)

    x = Dropout(rate=0.5)(x)
    x = Dense(units=confs.num_classes, kernel_regularizer=l2_reg)(x)
    output = Activation(activation='softmax')(x)

    model = Model(inputs=[input_1], outputs=[output])

    if confs.add_dog:
        if confs.dog_path == None or not os.path.exists(confs.dog_path):
            dog_model = keras.models.Sequential()
            dog_model.add(Conv2D(n_filters_dog, (3, 3), padding='same', input_shape=confs.x_train.shape[1:]))

            weights = dog_model.layers[0].get_weights()
            dogs = create_dog_layer(confs, n_filters_dog, kernel_size=3, nchannels=np.size(weights[0], 2))
            weights[0] = dogs
            dog_model.layers[0].set_weights(weights)

            dog_model.save(confs.dog_path)
        else:
            print('Reading the DoG file')
            dog_model = keras.models.load_model(confs.dog_path)
            weights = dog_model.layers[0].get_weights()
        model.layers[1].trainable = False
        model.layers[1].set_weights(weights)

    return model
