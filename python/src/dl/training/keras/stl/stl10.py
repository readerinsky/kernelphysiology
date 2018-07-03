from __future__ import print_function


import os
import sys


# finding the root of the project
current_path = os.getcwd()
python_root = 'kernelphysiology/python/'
project_dir = current_path.split(python_root, 1)[0]
python_root = os.path.join(project_dir, python_root)
sys.path += [os.path.join(python_root, 'src/')]


import urllib.request as urllib
import tarfile
import keras
import matplotlib.pyplot as plt
import numpy as np
from keras import backend as K, regularizers
from keras.engine.training import Model
from keras.layers import Add, Conv2D, MaxPooling2D, Dropout, Flatten, Dense, BatchNormalization, Activation, Input
from keras.callbacks import LearningRateScheduler, CSVLogger, ModelCheckpoint


# number of classes in the STL-10 dataset.
N_CLASSES = 10

# image shape
HEIGHT = 96
WIDTH = 96
DEPTH = 3

# size of a single image in bytes
SIZE = HEIGHT * WIDTH * DEPTH

# path to the directory with the data
DATA_DIR = os.path.join(python_root, 'data/datasets/stl/')

# url of the binary data
DATA_URL = 'http://ai.stanford.edu/~acoates/stl10/stl10_binary.tar.gz'

# path to the binary train file with image data
TRAIN_DATA_PATH = os.path.join(DATA_DIR, 'stl10/train_X.bin')

# path to the binary train file with labels
TRAIN_LABELS_PATH = os.path.join(DATA_DIR, 'stl10/train_y.bin')

# path to the binary test file with image data
TEST_DATA_PATH = os.path.join(DATA_DIR, 'stl10/test_X.bin')

# path to the binary test file with labels
TEST_LABELS_PATH = os.path.join(DATA_DIR, 'stl10/test_y.bin')

# path to class names file
CLASS_NAMES_PATH = os.path.join(DATA_DIR, 'stl10/class_names.txt')


def read_labels(path_to_labels):
    """
    :param path_to_labels: path to the binary file containing labels from the STL-10 dataset
    :return: an array containing the labels
    """
    with open(path_to_labels, 'rb') as f:
        labels = np.fromfile(f, dtype=np.uint8)
        return labels


def read_all_images(path_to_data):
    """
    :param path_to_data: the file containing the binary images from the STL-10 dataset
    :return: an array containing all the images
    """

    with open(path_to_data, 'rb') as f:
        # read whole file in uint8 chunks
        everything = np.fromfile(f, dtype=np.uint8)

        # We force the data into 3x96x96 chunks, since the
        # images are stored in "column-major order", meaning
        # that "the first 96*96 values are the red channel,
        # the next 96*96 are green, and the last are blue."
        # The -1 is since the size of the pictures depends
        # on the input file, and this way numpy determines
        # the size on its own.

        images = np.reshape(everything, (-1, 3, 96, 96))

        # Now transpose the images into a standard image format
        # readable by, for example, matplotlib.imshow
        # You might want to comment this line or reverse the shuffle
        # if you will use a learning algorithm like CNN, since they like
        # their channels separated.
        images = np.transpose(images, (0, 3, 2, 1))
        return images


def read_single_image(image_file):
    """
    CAREFUL! - this method uses a file as input instead of the path - so the
    position of the reader will be remembered outside of context of this method.
    :param image_file: the open file containing the images
    :return: a single image
    """
    # read a single image, count determines the number of uint8's to read
    image = np.fromfile(image_file, dtype=np.uint8, count=SIZE)
    # force into image matrix
    image = np.reshape(image, (3, 96, 96))
    # transpose to standard format
    # You might want to comment this line or reverse the shuffle
    # if you will use a learning algorithm like CNN, since they like
    # their channels separated.
    image = np.transpose(image, (2, 1, 0))
    return image


def plot_image(image):
    """
    :param image: the image to be plotted in a 3-D matrix format
    :return: None
    """
    plt.imshow(image)
    plt.show()


def save_image(image, name):
    for spine in plt.gca().spines.values():
        spine.set_visible(False)

    plt.tick_params(top=False, bottom=False, left=False, right=False, labelleft=False, labelbottom=True)
    plt.axis('off')
    
    plt.imshow(image)
    plt.savefig(name, bbox_inches='tight', dpi=96)


def download_and_extract():
    """
    Download and extract the STL-10 dataset
    :return: None
    """
    dest_directory = DATA_DIR
    if not os.path.exists(dest_directory):
        os.makedirs(dest_directory)
    filename = 'stl10'
    filepath = os.path.join(dest_directory, filename)
    if not os.path.exists(filepath):
        def _progress(count, block_size, total_size):
            sys.stdout.write('\rDownloading %s %.2f%%' % (filename,
                float(count * block_size) / float(total_size) * 100.0))
            sys.stdout.flush()
        filepath, _ = urllib.urlretrieve(DATA_URL, filepath, reporthook=_progress)
        print('Downloaded', filename)
        tarfile.open(filepath, 'r:gz').extractall(dest_directory)


def build_classifier_model(more_layers=0, add_batch_elu=True):
    n_conv_blocks = 5  # number of convolution blocks to have in our model.
    n_filters = 64  # number of filters to use in the first convolution block.
    l2_reg = regularizers.l2(2e-4)  # weight to use for L2 weight decay. 
    activation = 'elu'  # the activation function to use after each linear operation.

    if K.image_data_format() == 'channels_first':
        input_shape = (3, HEIGHT, WIDTH)
    else:
        input_shape = (HEIGHT, WIDTH, 3)

    x = input_1 = Input(shape=input_shape)
    
    # each convolution block consists of two sub-blocks of Conv->Batch-Normalization->Activation,
    # followed by a Max-Pooling and a Dropout layer.
    for i in range(n_conv_blocks):
        if i == 0:
            x = Conv2D(filters=n_filters, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
            if more_layers == 1:
                x = BatchNormalization()(x)
                x = Activation(activation=activation)(x)
            elif add_batch_elu:
                x = BatchNormalization()(x)
                x = Activation(activation=activation)(x)
                
            if more_layers == 2:
                # 
                x = Conv2D(filters=44, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                x = BatchNormalization()(x)
                x = Activation(activation=activation)(x)
            if more_layers == 3:
                # 
                x = Conv2D(filters=37, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                if add_batch_elu:
                    x = BatchNormalization()(x)
                    x = Activation(activation=activation)(x)
                
                #
                x = Conv2D(filters=37, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                x = BatchNormalization()(x)
                x = Activation(activation=activation)(x)   
            if more_layers == 4:
                # 
                x = Conv2D(filters=27, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                if add_batch_elu:
                    x = BatchNormalization()(x)
                    x = Activation(activation=activation)(x)
        
                #
                x = Conv2D(filters=64, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                if add_batch_elu:
                    x = BatchNormalization()(x)
                    x = Activation(activation=activation)(x)
    
                #
                x = Conv2D(filters=27, kernel_size=(3, 3), padding='same', kernel_regularizer=l2_reg)(x)
                x = BatchNormalization()(x)
                x = Activation(activation=activation)(x)
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
    x = Dense(units=N_CLASSES, kernel_regularizer=l2_reg)(x)
    output = Activation(activation='softmax')(x)

    return Model(inputs=[input_1], outputs=[output])


def train_classifier(x_train, y_train, x_test, y_test, model_output_path=None, batch_size=64, epochs=100, initial_lr=1e-3, more_layers=None):  
    def lr_scheduler(epoch):
        if epoch < 20:
            return initial_lr
        elif epoch < 40:
            return initial_lr / 2
        elif epoch < 50:
            return initial_lr / 4
        elif epoch < 60:
            return initial_lr / 8
        elif epoch < 70:
            return initial_lr / 16
        elif epoch < 80:
            return initial_lr / 32
        elif epoch < 90:
            return initial_lr / 64
        else:
            return initial_lr / 128

    model.compile(
        loss='categorical_crossentropy',
        optimizer=keras.optimizers.Adam(initial_lr),
        metrics=['accuracy']
    )

    model_name = 'keras_stl10_area_%d' % more_layers
    save_dir = '/home/arash/Software/repositories/kernelphysiology/python/data/nets/stl/stl10/'
    log_dir = os.path.join(save_dir, model_name)
    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)
    csv_logger = CSVLogger(os.path.join(log_dir, 'log.csv'), append=False, separator=';')
    check_points = ModelCheckpoint(os.path.join(log_dir, 'weights.{epoch:05d}.h5'), period=25)
    
    model.fit(x=x_train, y=y_train, batch_size=batch_size, epochs=epochs,
              verbose=1, validation_data=(x_test, y_test), 
              callbacks=[LearningRateScheduler(lr_scheduler), csv_logger, check_points])

    model_name += '.h5'
    model_output_path = os.path.join(save_dir, model_name)
    if model_output_path is not None:
        print('saving trained model to:', model_output_path)
        model.save(model_output_path)


def preprocess_input(img):
    img = img.astype('float32')
    img = (img - 127.5) / 127.5
    return img


def load_data(dirname=None):
    # download the extract the dataset.
    download_and_extract()

    # load the train and test data and labels.
    x_train = read_all_images(TRAIN_DATA_PATH)
    y_train = read_labels(TRAIN_LABELS_PATH)
    x_test = read_all_images(TEST_DATA_PATH)
    y_test = read_labels(TEST_LABELS_PATH)

    return (x_train, y_train), (x_test, y_test)

    
if __name__ == "__main__":
    (x_train, y_train), (x_test, y_test) = load_data()
    
    # convert all images to floats in the range [0, 1]
    x_train = preprocess_input(x_train)
    x_test = preprocess_input(x_test)
    
    # convert the labels to be zero based.
    y_train -= 1
    y_test -= 1

    # convert labels to hot-one vectors.
    y_train = keras.utils.to_categorical(y_train, N_CLASSES)
    y_test = keras.utils.to_categorical(y_test, N_CLASSES)

    more_layers = int(sys.argv[1])
    add_batch_elu = int(sys.argv[2]) == 1
    model = build_classifier_model(more_layers=more_layers, add_batch_elu=add_batch_elu)
    model.summary()

    train_classifier(x_train, y_train, x_test, y_test, more_layers=more_layers)