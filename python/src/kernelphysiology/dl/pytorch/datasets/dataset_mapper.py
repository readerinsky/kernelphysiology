# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import copy
import sys
import logging
import numpy as np
import random
import torch
from fvcore.common.file_io import PathManager

from detectron2.data import transforms as T
from detectron2.data import detection_utils as utils

from PIL import Image, ImageOps

from kernelphysiology.utils import imutils
from kernelphysiology.dl.utils.augmentation import get_testing_augmentations

"""
This file contains the default mapping that's applied to "dataset dicts".
"""

__all__ = ["DatasetMapper"]


def _read_image(file_name, format=None, vision_type='trichromat', contrast=None,
                opponent_space='lab', mosaic_pattern=None,
                manipulation_fun=None, manipulation_value=None):
    """
    Read an image into the given format.
    Will apply rotation and flipping if the image has such exif information.

    Args:
        file_name (str): image file path
        format (str): one of the supported image modes in PIL, or "BGR"

    Returns:
        image (np.ndarray): an HWC image in the given format.
    """
    with PathManager.open(file_name, "rb") as f:
        image = Image.open(f).convert('RGB')
        image = np.asarray(image).copy()
        # FIXME: right now only for chromaticity manipulations
        if manipulation_fun is not None:
            image = manipulation_fun(image, manipulation_value)

        if contrast is not None:
            # FIXME: nicer solution
            if type(contrast) is list:
                amount = random.uniform(contrast, 1)
            else:
                amount = contrast
            image = np.uint8(imutils.adjust_contrast(image, amount))

        if vision_type != 'trichromat':
            if vision_type == 'monochromat':
                image = imutils.reduce_chromaticity(image, 0, opponent_space)
            elif vision_type == 'dichromat_yb':
                image = imutils.reduce_yellow_blue(image, 0, opponent_space)
            elif vision_type == 'dichromat_rg':
                image = imutils.reduce_red_green(image, 0, opponent_space)
            else:
                sys.exit('Not supported vision type %s' % vision_type)

        if mosaic_pattern != "" and mosaic_pattern is not None:
            image = np.uint8(imutils.im2mosaic(image, mosaic_pattern))

        image = Image.fromarray(image)

        # capture and ignore this bug:
        # https://github.com/python-pillow/Pillow/issues/3973
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        if format is not None:
            # PIL only supports RGB, so convert to RGB and flip channels over
            # below
            conversion_format = format
            if format == "BGR":
                conversion_format = "RGB"
            image = image.convert(conversion_format)
        image = np.asarray(image)
        if format == "BGR":
            # flip channels if needed
            image = image[:, :, ::-1]
        # PIL squeezes out the channel dimension for "L", so make it HWC
        if format == "L":
            image = np.expand_dims(image, -1)
        return image


class DatasetMapper:
    """
    A callable which takes a dataset dict in Detectron2 Dataset format,
    and map it into a format used by the model.

    This is the default callable to be used to map your dataset dict into
    training data.
    You may need to follow it to implement your own one for customized logic.

    The callable currently does the following:

    1. Read the image from "file_name"
    2. Applies cropping/geometric transforms to the image and annotations
    3. Prepare data and annotations to Tensor and :class:`Instances`
    """

    def __init__(self, cfg, is_train=True):
        if cfg.INPUT.CROP.ENABLED and is_train:
            self.crop_gen = T.RandomCrop(
                cfg.INPUT.CROP.TYPE, cfg.INPUT.CROP.SIZE
            )
            logging.getLogger(__name__).info(
                "CropGen used in training: " + str(self.crop_gen))
        else:
            self.crop_gen = None

        self.tfm_gens = utils.build_transform_gen(cfg, is_train)

        # fmt: off
        self.img_format = cfg.INPUT.FORMAT
        self.mask_on = cfg.MODEL.MASK_ON
        self.mask_format = cfg.INPUT.MASK_FORMAT
        self.keypoint_on = cfg.MODEL.KEYPOINT_ON
        self.load_proposals = cfg.MODEL.LOAD_PROPOSALS
        # fmt: on
        if self.keypoint_on and is_train:
            # Flip only makes sense in training
            self.keypoint_hflip_indices = utils.create_keypoint_hflip_indices(
                cfg.DATASETS.TRAIN)
        else:
            self.keypoint_hflip_indices = None

        if self.load_proposals:
            self.min_box_side_len = cfg.MODEL.PROPOSAL_GENERATOR.MIN_SIZE
            self.proposal_topk = (
                cfg.DATASETS.PRECOMPUTED_PROPOSAL_TOPK_TRAIN
                if is_train
                else cfg.DATASETS.PRECOMPUTED_PROPOSAL_TOPK_TEST
            )
        self.is_train = is_train
        self.vision_type = cfg.INPUT.VISION_TYPE
        self.manipulation_type = cfg.INPUT.INFER_MANIPULATION_TYPE
        self.manipulation_fun = None
        if self.manipulation_type != "":
            supported_manipulations = get_testing_augmentations()
            self.manipulation_fun = supported_manipulations[
                self.manipulation_type]
        self.manipulation_value = cfg.INPUT.INFER_MANIPULATION_VALUE
        self.opponent_space = cfg.INPUT.OPPONENT_SPACE
        self.contrast = cfg.INPUT.CONTRAST
        self.mosaic_pattern = cfg.INPUT.MOSAIC_PATTERN
        if self.contrast == 1.0:
            self.contrast = None

    def __call__(self, dataset_dict):
        """
        Args:
            dataset_dict (dict): Metadata of one image, in Detectron2 Dataset
            format.

        Returns:
            dict: a format that builtin models in detectron2 accept
        """
        dataset_dict = copy.deepcopy(
            dataset_dict)  # it will be modified by code below
        # USER: Write your own image loading if it's not from a file
        image = _read_image(
            dataset_dict["file_name"], format=self.img_format,
            vision_type=self.vision_type, contrast=self.contrast,
            opponent_space=self.opponent_space,
            mosaic_pattern=self.mosaic_pattern,
            manipulation_fun=self.manipulation_fun,
            manipulation_value=self.manipulation_value
        )
        utils.check_image_size(dataset_dict, image)

        if "annotations" not in dataset_dict:
            image, transforms = T.apply_transform_gens(
                ([self.crop_gen] if self.crop_gen else []) + self.tfm_gens,
                image
            )
        else:
            # Crop around an instance if there are instances in the image.
            # USER: Remove if you don't use cropping
            if self.crop_gen:
                crop_tfm = utils.gen_crop_transform_with_instance(
                    self.crop_gen.get_crop_size(image.shape[:2]),
                    image.shape[:2],
                    random.choice(dataset_dict["annotations"]),
                )
                image = crop_tfm.apply_image(image)
            image, transforms = T.apply_transform_gens(self.tfm_gens, image)
            if self.crop_gen:
                transforms = crop_tfm + transforms

        image_shape = image.shape[:2]  # h, w

        # Pytorch's dataloader is efficient on torch.Tensor due to
        # shared-memory, but not efficient on large generic data structures due
        # to the use of pickle & mp.Queue.
        # Therefore it's important to use torch.Tensor.
        dataset_dict["image"] = torch.as_tensor(
            np.ascontiguousarray(image.transpose(2, 0, 1)))

        # USER: Remove if you don't use pre-computed proposals.
        if self.load_proposals:
            utils.transform_proposals(
                dataset_dict, image_shape, transforms, self.min_box_side_len,
                self.proposal_topk
            )

        if not self.is_train:
            # USER: Modify this if you want to keep them for some reason.
            dataset_dict.pop("annotations", None)
            dataset_dict.pop("sem_seg_file_name", None)
            return dataset_dict

        if "annotations" in dataset_dict:
            # USER: Modify this if you want to keep them for some reason.
            for anno in dataset_dict["annotations"]:
                if not self.mask_on:
                    anno.pop("segmentation", None)
                if not self.keypoint_on:
                    anno.pop("keypoints", None)

            # USER: Implement additional transformations if you have other types
            # of data
            annos = [
                utils.transform_instance_annotations(
                    obj, transforms, image_shape,
                    keypoint_hflip_indices=self.keypoint_hflip_indices
                )
                for obj in dataset_dict.pop("annotations")
                if obj.get("iscrowd", 0) == 0
            ]
            instances = utils.annotations_to_instances(
                annos, image_shape, mask_format=self.mask_format
            )
            # Create a tight bounding box from masks, useful when image is
            # cropped
            if self.crop_gen and instances.has("gt_masks"):
                instances.gt_boxes = instances.gt_masks.get_bounding_boxes()
            dataset_dict["instances"] = utils.filter_empty_instances(instances)

        # USER: Remove if you don't do semantic/panoptic segmentation.
        if "sem_seg_file_name" in dataset_dict:
            with PathManager.open(
                    dataset_dict.pop("sem_seg_file_name"), "rb"
            ) as f:
                sem_seg_gt = Image.open(f)
                sem_seg_gt = np.asarray(sem_seg_gt, dtype="uint8")
            sem_seg_gt = transforms.apply_segmentation(sem_seg_gt)
            sem_seg_gt = torch.as_tensor(np.long(sem_seg_gt))
            dataset_dict["sem_seg"] = sem_seg_gt
        return dataset_dict
