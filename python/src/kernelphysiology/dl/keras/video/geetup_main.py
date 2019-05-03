from keras.models import Sequential
from keras.layers import Reshape, Input, UpSampling2D, Concatenate
from keras.layers.convolutional import Conv3D, Conv2D
from keras.layers.convolutional_recurrent import ConvLSTM2D
from keras.layers.normalization import BatchNormalization
import numpy as np
import pylab as plt
import keras
from keras.callbacks import LearningRateScheduler, ModelCheckpoint
from functools import partial

from keras.layers.wrappers import TimeDistributed
from keras.layers.convolutional import MaxPooling3D, MaxPooling2D
import glob
from skimage import io, color, transform
import sys
import os

from kernelphysiology.filterfactory import gaussian


def lr_schedule_resnet(epoch, lr):
    new_lr = lr * (0.1 ** (epoch // (90 / 3)))
    return new_lr


def show_sample(sample):
    sample = sample.squeeze()
    n_frames = sample.shape[0]
    fig = plt.figure(figsize=(14, 2))
    for i in range(sample.shape[0]):
        plt.subplot(2, round(n_frames / 2), i + 1)
        to_be_displayed = sample[i,].squeeze()  # / sample[i, ].max()
        plt.imshow(to_be_displayed, cmap='gray')


def show_results(sample, gt, predict):
    sample = sample.squeeze()
    gt = gt.squeeze()
    predict = predict.squeeze()
    n_frames = sample.shape[0]
    fig = plt.figure(figsize=(14, 2))

    for i in range(sample.shape[0]):
        plt.subplot(2, round(n_frames / 2), i + 1)
        to_be_displayed = sample[i,].squeeze()  # / sample[i, ].max()
        top_layer = gt[i,].squeeze()  # / gt[i, ].max()
        im1 = plt.imshow(to_be_displayed, cmap=plt.cm.gray)
        im2 = plt.imshow(top_layer, cmap=plt.cm.viridis, alpha=.5)

    fig = plt.figure(figsize=(14, 2))

    for i in range(sample.shape[0]):
        plt.subplot(2, round(n_frames / 2), i + 1)
        to_be_displayed = sample[i,].squeeze()  # / sample[i, ].max()
        top_layer = predict[i,].squeeze()  # / predict[i, ].max()
        im1 = plt.imshow(to_be_displayed, cmap=plt.cm.gray)
        im2 = plt.imshow(top_layer, cmap=plt.cm.viridis, alpha=.5)


def inv_normalise_tensor(tensor, mean, std):
    tensor = tensor.copy()
    # inverting the normalisation for each channel
    for i in range(tensor.shape[4]):
        tensor[:, :, :, :, i] = (tensor[:, :, :, :, i] * std[i]) + mean[i]
    tensor = tensor.clip(0, 1)
    return tensor


def normalise_tensor(tensor, mean, std):
    tensor = tensor.copy()
    print(tensor.shape)
    # normalising the channels
    for i in range(tensor.shape[4]):
        tensor[:, :, :, :, i] = (tensor[:, :, :, :, i] - mean[i]) / std[i]
    return tensor


def read_data(dataset_dir):
    input_frames = []
    fixation_points = []
    for i, subject_dir in enumerate(glob.glob(dataset_dir + '/*/segments/1/')):
        if i == 20:
            break
        current_input_frames, current_fixation_points = \
            read_one_directory(subject_dir)
        input_frames.extend(current_input_frames)
        fixation_points.extend(current_fixation_points)
    input_frames = np.array(input_frames)
    fixation_points = np.array(fixation_points)
    return input_frames, fixation_points


def read_one_directory(dataset_dir):
    frames_gap = 10
    # n_frames = 10
    # n_samples = len(glob.glob(dataset_dir + '/*/'))
    rows = 40
    cols = 40
    chns = 1
    input_frames = []
    fixation_points = []
    g_fix = gaussian.gaussian_kernel2(1.5, 1.5)
    for video_dir in glob.glob(dataset_dir + '/*/'):
        video_ind = video_dir.split('/')[-2].split('_')[-1]
        fixation_array = np.loadtxt(
            dataset_dir + 'SUBSAMP_EYETR_' + video_ind + '.txt')
        current_num_frames = len(glob.glob((video_dir + '/*.jpg')))
        selected_frame_infs = [*range(0, current_num_frames, frames_gap)]
        acceptable_frame_seqs = len(selected_frame_infs) - frames_gap
        if acceptable_frame_seqs < 0:
            continue
        current_input_frames = np.zeros(
            (acceptable_frame_seqs, frames_gap, rows, cols, chns),
            dtype=np.float)
        current_fixation_points = np.zeros(
            (acceptable_frame_seqs, frames_gap, rows, cols, 1),
            dtype=np.float)
        for i in range(acceptable_frame_seqs + frames_gap - 1):
            img_ind = selected_frame_infs[i]
            current_img = io.imread(
                video_dir + '/frames' + str(img_ind + 1) + '.jpg')
            current_img = color.rgb2gray(current_img).astype('float') / 255
            org_rows = current_img.shape[0]
            org_cols = current_img.shape[1]
            current_img = transform.resize(current_img, (rows, cols))

            current_fixation = np.zeros((rows, cols, 1))
            if fixation_array[img_ind, 1] > 0 and fixation_array[
                img_ind, 0] > 0:
                fpr = int(fixation_array[img_ind, 1] * (rows / org_rows))
                fpc = int(fixation_array[img_ind, 0] * (cols / org_cols))

                sr = fpr - (g_fix.shape[0] // 2)
                sc = fpc - (g_fix.shape[1] // 2)
                # making sure they're within the range of image
                gsr = np.maximum(0, -sr)
                gsc = np.maximum(0, -sc)

                er = sr + g_fix.shape[0]
                ec = sc + g_fix.shape[1]
                # making sure they're within the range of image
                sr = np.maximum(0, sr)
                sc = np.maximum(0, sc)

                er_diff = er - current_img.shape[0]
                ec_diff = ec - current_img.shape[1]
                ger = np.minimum(g_fix.shape[0], g_fix.shape[0] - er_diff)
                gec = np.minimum(g_fix.shape[1], g_fix.shape[1] - ec_diff)

                er = np.minimum(er, current_img.shape[0])
                ec = np.minimum(ec, current_img.shape[1])

                current_fixation[sr:er, sc:ec, 0] = g_fix[gsr:ger,
                                                    gsc:gec] / g_fix[gsr:ger,
                                                               gsc:gec].max()
            for j in range(i, i+frames_gap):
                current_ind = i
                if (i - j) < frames_gap and current_ind < acceptable_frame_seqs:
                    current_input_frames[current_ind, i - j, :, :,
                    0] = current_img
                    current_fixation_points[
                        current_ind, i - j,] = current_fixation
        input_frames.extend(current_input_frames)
        fixation_points.extend(current_fixation_points)

    input_frames = np.array(input_frames)
    fixation_points = np.array(fixation_points)
    input_frames = normalise_tensor(input_frames, [0.5], [0.25])
    return input_frames, fixation_points

def class_net_fcn_2p_lstm(input_shape):
    c = 16
    input_img = Input(input_shape, name='input')
    x = ConvLSTM2D(filters=c, kernel_size=(3, 3), padding='same',
                   return_sequences=True)(input_img)
    x = BatchNormalization()(x)
    x = ConvLSTM2D(filters=c, kernel_size=(3, 3), padding='same',
                   return_sequences=True)(x)
    x = BatchNormalization()(x)
    c1 = ConvLSTM2D(filters=c, kernel_size=(3, 3), padding='same',
                    return_sequences=True)(x)

    x = TimeDistributed(MaxPooling2D((2, 2), (2, 2)))(c1)

    x = ConvLSTM2D(filters=2 * c, kernel_size=(3, 3), padding='same',
                   return_sequences=True)(x)
    x = BatchNormalization()(x)
    x = ConvLSTM2D(filters=2 * c, kernel_size=(3, 3), padding='same',
                   return_sequences=True)(x)
    x = BatchNormalization()(x)
    c2 = ConvLSTM2D(filters=2 * c, kernel_size=(3, 3), padding='same',
                    return_sequences=True)(x)

    x = TimeDistributed(MaxPooling2D((2, 2), (2, 2)))(c2)
    x = ConvLSTM2D(filters=2 * c, kernel_size=(3, 3), padding='same',
                   return_sequences=True)(x)
    x = BatchNormalization()(x)
    x = ConvLSTM2D(filters=2 * c, kernel_size=(3, 3), padding='same',
                   return_sequences=True)(x)
    x = BatchNormalization()(x)
    c3 = ConvLSTM2D(filters=2 * c, kernel_size=(3, 3), padding='same',
                    return_sequences=True)(x)

    x = TimeDistributed(UpSampling2D((2, 2)))(c3)
    x = Concatenate()([c2, x])
    x = TimeDistributed(Conv2D(c, kernel_size=(3, 3), padding='same'))(x)

    x = TimeDistributed(UpSampling2D((2, 2)))(x)
    x = Concatenate()([c1, x])
    # x = TimeDistributed(Convolution2D(c, 3, 3, border_mode='same'))(x)

    #     x = TimeDistributed(Conv2D(3, kernel_size=(3, 3), padding='same'))(x)
    #     x = TimeDistributed(UpSampling2D((2, 2)))(x)
    #     x = TimeDistributed(Conv2D(3, kernel_size=(3, 3), padding='same'))(x)
    #     x = TimeDistributed(UpSampling2D((2, 2)))(x)

    output = TimeDistributed(
        Conv2D(1, kernel_size=(3, 3), padding='same', activation='sigmoid'),
        name='output')(x)

    model = keras.models.Model(input_img, output)
    #     loss = categorical_crossentropy_3d_w(10, class_dim=-1)
    opt = keras.optimizers.SGD(lr=0.1, decay=0, momentum=0.9, nesterov=False)
    model.compile(loss='binary_crossentropy', optimizer=opt)
    return model


lr_schedule_lambda = partial(lr_schedule_resnet, lr=0.1)
input_frames, fixation_points = read_data(sys.argv[1])

seq = class_net_fcn_2p_lstm(input_frames.shape[1:])
last_checkpoint_logger = ModelCheckpoint('model_weights_last.h5', verbose=1,
                                         save_weights_only=True, save_best_only=False)

os.environ['CUDA_VISIBLE_DEVICES'] = '3'
seq.fit(input_frames,
        fixation_points,
        #         np.reshape(fixation_points[:1000,], (-1, n_frames, rows * cols, 1)),
        batch_size=64, epochs=90,
        validation_split=0.25,
        callbacks=[LearningRateScheduler(lr_schedule_lambda, last_checkpoint_logger)])
