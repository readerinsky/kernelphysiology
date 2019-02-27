'''
Common blocks for various architecture.
'''


from keras import layers
from keras.layers import Activation
from keras.layers import Conv2D
from keras.layers import BatchNormalization
from keras.regularizers import l2
from keras import backend as K


# FIXME: kernel_size of tupple
def pyramid_block(x, num_filters, kernel_size, name_base=None,
                  strides=(1, 1), padding='same', dilation_rate=(1, 1),
                  kernel_constraint=None, kernel_initializer='he_normal',
                  activation_type='relu', conv_first=True,
                  batch_normalization=True,
                  num_levels=4):
    if num_levels == 1 or kernel_size == 1:
        x = conv_norm_rect(x, num_filters, kernel_size, name_base=name_base,
                           strides=strides, padding=padding, dilation_rate=dilation_rate,
                           kernel_constraint=kernel_constraint,
                           kernel_initializer=kernel_initializer,
                           activation_type=activation_type,
                           conv_first=conv_first,
                           batch_normalization=batch_normalization)
        return x

    filters_level = round(num_filters / num_levels)
    f_0 = num_filters - (filters_level * num_levels)

    xis = []
    for i in range(num_levels):
        num_kernels = filters_level
        # to compensate for rounding
        if i == 0:
            num_kernels += f_0
        rf_size = kernel_size + (i * 2)
        if name_base is not None:
            name = '%s_%02d' % (name_base, i)
        else:
            name = None
        xi = conv_norm_rect(x, num_kernels, rf_size, name_base=name,
                            strides=strides, padding=padding, dilation_rate=dilation_rate,
                            kernel_constraint=kernel_constraint,
                            kernel_initializer=kernel_initializer,
                            activation_type=activation_type,
                            conv_first=conv_first,
                            batch_normalization=batch_normalization)
        xis.append(xi)
    x = layers.Concatenate()(xis)
    return x


# TODO: make common arguments
def conv_norm_rect(x, num_kernels, rf_size, name_base, strides=(1, 1), padding='same',
                   dilation_rate=(1, 1), kernel_constraint=None, kernel_initializer='he_normal',
                   activation_type='relu', conv_first=True,
                   batch_normalization=True):
    if K.image_data_format() == 'channels_last':
        bn_axis = 3
    else:
        bn_axis = 1
    if name_base is not None:
        name_conv = name_base + '_conv'
        name_norm = name_base + '_norm'
        name_rect = name_base + '_rect'
    else:
        name_conv = None
        name_norm = None
        name_rect = None

    # TODO: is regualiser necessary
    conv = Conv2D(num_kernels, rf_size, strides=strides,
                  dilation_rate=dilation_rate,
                  kernel_constraint=kernel_constraint,
                  kernel_initializer=kernel_initializer,
                  padding=padding, name=name_conv,
                  kernel_regularizer=l2(1e-4))
    if conv_first:
        x = conv(x)
        if batch_normalization:
            x = BatchNormalization(axis=bn_axis, name=name_norm)(x)
        if activation_type is not None:
            x = Activation(activation_type, name=name_rect)(x)
    else:
        if batch_normalization:
            x = BatchNormalization(axis=bn_axis, name=name_norm)(x)
        if activation_type is not None:
            x = Activation(activation_type, name=name_rect)(x)
        x = conv(x)

    return x