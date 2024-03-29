import torch

from pathlib import Path
from train import UNet_cooler, MapsDataModule
import matplotlib.pyplot as plt

MODEL_PATH = "sampling_cnn_vol3_32.pth"
BASE_PATH = Path('/home/czarek/mgr/eval_data')

model = UNet_cooler()
model.load_state_dict(torch.load(MODEL_PATH))

model.eval()


data_module = MapsDataModule(main_path=BASE_PATH)
data_module.setup("test")

batch_size = 1
sampler = torch.utils.data.RandomSampler(data_module.train_dataset)

dataloader = torch.utils.data.DataLoader(
    data_module.train_dataset,
    batch_size=batch_size,
    sampler=sampler,
    num_workers=data_module._num_workers
)

batch = next(iter(dataloader))
# print(batch)
image, mask, coords = batch
print(coords.data.tolist()[0][0])
image_show = image.detach().cpu().numpy()
image_show = image_show.transpose((0, 2, 3, 1))
# print(image_show)
# plt.imshow(image_show[0])
# plt.show()

with torch.no_grad():
    output = model(image, coords)
    clipped = torch.clamp(output, min=-3, max=1)
    # print(model)
# make_dot(output, params=dict(list(model.named_parameters()))).render("torchviz", format="png")

# model_graph = draw_graph(model, input_data=(image, coords), expand_nested=True, save_graph=True, filename='torchview')

x_start = coords.data.tolist()[0][0][0][0]
y_start = coords.data.tolist()[0][0][0][1]
x_finish = coords.data.tolist()[0][0][1][0]
y_finish = coords.data.tolist()[0][0][1][1]
start = (y_start, x_start)
finish = (y_finish, x_finish)


# f, axarr = plt.subplots(1, 4)
# x_np = image.detach().cpu().numpy()
# x_np = x_np.transpose((0, 2, 3, 1))
#
# y_np = mask.detach().cpu().numpy()
# y_np = y_np.transpose((0, 2, 3, 1))
#
# y_hat_np = output.detach().cpu().numpy()
# y_hat_np = y_hat_np.transpose((0, 2, 3, 1))
#
# clipped = clipped.detach().cpu().numpy()
# clipped = clipped.transpose((0, 2, 3, 1))
#
# axarr[0].imshow(x_np[0])
# axarr[0].scatter(x_start, y_start, c='g', marker='o', s=30, label='Start')
# axarr[0].scatter(x_finish, y_finish, c='r', marker='o', s=30, label='Finish')
# axarr[1].imshow(y_np[0])
# axarr[2].imshow(y_hat_np[0])
# axarr[3].imshow(clipped[0])
# plt.show()


f, axarr = plt.subplots(1, 3)
x_np = image.detach().cpu().numpy()
x_np = x_np.transpose((0, 2, 3, 1))

y_np = mask.detach().cpu().numpy()
y_np = y_np.transpose((0, 2, 3, 1))

clipped = clipped.detach().cpu().numpy()
clipped = clipped.transpose((0, 2, 3, 1))

axarr[0].imshow(x_np[0])
axarr[0].scatter(x_start, y_start, c='g', marker='o', s=300, label='Start')
axarr[0].scatter(x_finish, y_finish, c='r', marker='o', s=300, label='Finish')
axarr[1].imshow(y_np[0])
axarr[2].imshow(clipped[0])
plt.show()
