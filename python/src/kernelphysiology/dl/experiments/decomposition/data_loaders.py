"""
Data-loader for multiple outputs.
"""

import os
import numpy as np

from torchvision import datasets as tdatasets

from kernelphysiology.utils import path_utils


def _apply_transforms(imgin, intransform, outtransform, transform):
    imgout = imgin.copy()
    if intransform is not None:
        imgin = intransform(imgin)
    if outtransform is not None:
        imgout = outtransform([imgout, imgin.copy()])

    if transform is not None:
        imgin, imgout = transform([imgin, imgout])
    return imgin, imgout


class ImageFolder(tdatasets.ImageFolder):
    def __init__(self, intransform=None, outtransform=None, **kwargs):
        super(ImageFolder, self).__init__(**kwargs)
        self.imgs = self.samples
        self.intransform = intransform
        self.outtransform = outtransform

    def __getitem__(self, index):
        path, class_target = self.samples[index]
        imgin = self.loader(path)
        imgin = np.asarray(imgin).copy()
        imgin, imgout = _apply_transforms(
            imgin, self.intransform, self.outtransform, self.transform
        )

        # right now we're not using the class target, but perhaps in the future
        if self.target_transform is not None:
            class_target = self.target_transform(class_target)

        return imgin, imgout, path


class OneFolder(tdatasets.VisionDataset):
    def __init__(self, intransform=None, outtransform=None, **kwargs):
        super(OneFolder, self).__init__(**kwargs)
        self.samples = path_utils.image_in_folder(self.root)
        print('Read %d images.' % len(self.samples))
        self.loader = tdatasets.folder.pil_loader
        self.intransform = intransform
        self.outtransform = outtransform

    def __getitem__(self, index):
        path = self.samples[index]
        imgin = self.loader(path)
        imgin = np.asarray(imgin).copy()
        imgin, imgout = _apply_transforms(
            imgin, self.intransform, self.outtransform, self.transform
        )

        return imgin, imgout, path

    def __len__(self):
        return len(self.samples)


class CategoryImages(OneFolder):
    def __init__(self, root, category, **kwargs):
        kwargs['root'] = os.path.join(root, category)
        super(CategoryImages, self).__init__(**kwargs)


class CelebA(tdatasets.CelebA):
    def __init__(self, intransform=None, outtransform=None, **kwargs):
        super(CelebA, self).__init__(**kwargs)
        self.loader = tdatasets.folder.pil_loader
        self.intransform = intransform
        self.outtransform = outtransform

    def __getitem__(self, index):
        path = os.path.join(
            self.root, self.base_folder, "img_align_celeba",
            self.filename[index]
        )
        imgin = self.loader(path)
        imgin = np.asarray(imgin).copy()
        imgin, imgout = _apply_transforms(
            imgin, self.intransform, self.outtransform, self.transform
        )

        target = []
        for t in self.target_type:
            if t == "attr":
                target.append(self.attr[index, :])
            elif t == "identity":
                target.append(self.identity[index, 0])
            elif t == "bbox":
                target.append(self.bbox[index, :])
            elif t == "landmarks":
                target.append(self.landmarks_align[index, :])
            else:
                # TODO: refactor with utils.verify_str_arg
                raise ValueError(
                    "Target type \"{}\" is not recognized.".format(t)
                )
        if target:
            target = tuple(target) if len(target) > 1 else target[0]

            if self.target_transform is not None:
                target = self.target_transform(target)
        else:
            target = None

        return imgin, imgout, path
