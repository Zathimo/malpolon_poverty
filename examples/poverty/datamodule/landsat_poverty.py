
import os
import random

import numpy as np
import rasterio
import pandas as pd
from matplotlib import pyplot

import torch
from torch.utils.data import Dataset
from torch.utils.data import DataLoader, random_split
import torchvision
from torchvision import transforms
import pytorch_lightning as pl




# TODO : Add JITTER and NORMALIZER to transfomer LightningDataModule, top remove ``preprocess_landsat`` step,
# TODO : tile = preprocess_landsat(tile, self.normalizer['landsat_+_nightlights'], JITTER)


NORMALIZER = 'dataset/normalizer.pkl'
BANDS = ['BLUE', 'GREEN', 'RED', 'NIR', 'SWIR1', 'SWIR2', 'TEMP1', 'NIGHTLIGHTS']
DESCRIPTOR = {
    'cluster': "float",
    'lat': "float",
    "lon": "float",
    'wealthpooled': "float",
    'BLUE': "float",
    'GREEN': "float",
    'RED': "float",
    'NIR': "float",
    'SWIR1': "float",
    'SWIR2': "float",
    'TEMP1': "float",
    'NIGHTLIGHTS': "float"
}

JITTER =transforms.ColorJitter(brightness=0.1, contrast=0.1)


def preprocess_landsat(raster, normalizer, jitter=None):
    for i in range(7):

        # Color Jittering transform
        tmp_shape = raster[i].shape
        if jitter:
            raster[i] = torch.reshape(
                jitter(raster[i][None, :, :]),
                tmp_shape
            )

        # Dataset normalization
        raster[i] = (raster[i] - normalizer[0][i]) / (normalizer[1][i])

    return raster



class PovertyDataModule(pl.LightningDataModule):
    def __init__(
            self,  
            tif_dir : str = 'landsat_tiles/', 
            dataset_path: str = 'examples/poverty/dataset/',
            labels_name: str = 'observation_2013+.csv',
            train_batch_size: int = 32,
            inference_batch_size: int = 16,
            num_workers: int = 8,
            
            cach_data: bool = True,
            val_split : float = 0.2,
            # transform=None,
            **kwargs
        ):
        super().__init__()
        self.dataframe = pd.read_csv(dataset_path+labels_name)
        self.tif_dir = dataset_path+tif_dir
        self.train_batch_size = train_batch_size
        self.inference_batch_size = inference_batch_size
        self.transform = torch.nn.Sequential(
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.RandomHorizontalFlip(),
            torchvision.transforms.RandomVerticalFlip()
        )
        self.val_split = val_split
        self.num_workers = num_workers
        
    def get_dataset(self):
        dataset = MSDataset(self.dataframe, self.tif_dir)
        return dataset

    def setup(self, stage=None):
        full_dataset = MSDataset(self.dataframe, self.tif_dir)
        
        val_size = int(len(full_dataset) * self.val_split)
        train_size = len(full_dataset) - val_size
        self.train_dataset, self.val_dataset = random_split(full_dataset, [train_size, val_size])

    def train_dataloader(self):
        return DataLoader(self.train_dataset, batch_size=self.train_batch_size, shuffle=True, num_workers=self.num_workers)

    def val_dataloader(self):
        return DataLoader(self.val_dataset, batch_size=self.inference_batch_size, num_workers=self.num_workers)


class MSDataset(Dataset):

    def __init__(self, dataframe, root_dir):
        """
        Args:
            dataframe (Pandas DataFrame): Pandas DataFrame containing image file names and labels.
            root_dir (string): Directory with all the images.
        """
        self.dataframe = dataframe
        self.root_dir = root_dir

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, idx):

        if torch.is_tensor(idx):
            idx = idx.tolist()


        row = self.dataframe.iloc[idx]

        value = row.wealthpooled.astype('float')
        
        tile_name = os.path.join(self.root_dir,
                                 str(row.country) + "_" + str(row.year),
                                 str(row.cluster) + ".tif"
                                 )

        tile = np.empty([7, 255, 255])

        with rasterio.open(tile_name) as src:
        
            for band in src.indexes[0:-1]:
                tile[band-1, :, :] = src.read(band)

        tile = np.nan_to_num(tile)

        return torch.tensor(tile, dtype=torch.float32), torch.tensor(value, dtype=torch.float32)
    
    def plot(self, idx, rgb=False):

        tile, value = self.__getitem__(idx)
        max,_= tile.max(dim=1)
        max,_= max.max(dim=1)
        print(max)
        tile=tile.numpy()
        
        if rgb:
            fig, ax = pyplot.subplots(1, 1, figsize=(6, 6))
            img_rgb=tile[0:3, ...][::-1, ... ].transpose(1,2,0)
            ax.imshow(img_rgb,vmax=50) #
            ax.set_title(f"Value: {value}, RGB")
        else :

            fig, axs = pyplot.subplots(2, 4, figsize=(12, 6))

            for i, ax in enumerate(axs.flat[0:-1]):

                ax.imshow(tile[i, ...], cmap='pink')

                ax.set_title(f"Band: {i}")
            fig.suptitle(f"Value: {value}")

            pyplot.tight_layout()
            pyplot.show()


if __name__ == '__main__':
    module = PovertyDataModule()
    module.setup()
    module.train_dataloader()
    module.val_dataloader()
    module.get_dataset()
    