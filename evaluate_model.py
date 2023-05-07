import torch

from pathlib import Path
from train import UNet_cooler, MapsDataModule, MODEL_PATH
import matplotlib.pyplot as plt

BASE_PATH = Path('/home/czarek/mgr/maps')

model = UNet_cooler()
model.load_state_dict(torch.load(MODEL_PATH))

model.eval()


data_module = MapsDataModule(main_path=BASE_PATH)
data_module.setup("test")

batch_size = 2
sampler = torch.utils.data.RandomSampler(data_module.train_dataset)

dataloader = torch.utils.data.DataLoader(
    data_module.train_dataset,
    batch_size=batch_size,
    sampler=sampler,
    num_workers=data_module._num_workers
)

batch = next(iter(dataloader))
print(batch)
image, mask, coords = batch


with torch.no_grad():
    output = model(image, coords)

f, axarr = plt.subplots(1, 3)
x_np = image.detach().cpu().numpy()
x_np = x_np.transpose((0, 2, 3, 1))
y_np = mask.detach().cpu().numpy()
y_np = y_np.transpose((0, 2, 3, 1))
y_hat_np = output.detach().cpu().numpy()
y_hat_np = y_hat_np.transpose((0, 2, 3, 1))
axarr[0].imshow(x_np[0])
axarr[1].imshow(y_np[0])
axarr[2].imshow(y_hat_np[0])
plt.show()
