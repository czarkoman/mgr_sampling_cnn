import torch
import random
import math
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import distance
from pathlib import Path
from time import perf_counter

from train import UNet_cooler, MapsDataModule, MODEL_PATH

BASE_PATH = Path('/home/czarek/mgr/maps')
# np.set_printoptions(threshold=sys.maxsize)


def get_blank_maps_list() -> list:
    maps_list = [str(image_path) for image_path in sorted((BASE_PATH / 'images').iterdir())]
    return maps_list


def get_start_finish_coordinates(path: str) -> tuple:
    x_start = int(get_from_string(path, "_sx", "_sy"))
    y_start = int(get_from_string(path, "_sy", "_fx"))
    x_finish = int(get_from_string(path, "_fx", "_fy"))
    y_finish = int(get_from_string(path, "_fy", ".png"))

    return (y_start, x_start), (y_finish, x_finish)


def get_from_string(path: str, start: str, finish: str) -> str:
    start_index = path.find(start)
    end_index = path.find(finish)

    substring = path[start_index+3:end_index]

    return substring


class Node:
    def __init__(self, position, cost=0):
        self.position = position
        self.parent = None
        self.children = []
        self.cost = cost


class RRTStar:
    def __init__(self, occ_map, heat_map, start, goal, max_iterations, max_step_size, nearby_nodes_radius,
                 goal_threshold, neural_bias):
        self.start_node = Node(start)
        self.goal = goal
        self.max_iterations = max_iterations
        self.max_step_size = max_step_size
        self.radius = nearby_nodes_radius
        self.goal_threshold = goal_threshold
        self.nodes = [self.start_node]
        self.occ_map = np.dot(occ_map[..., :3], [0.2989, 0.5870, 0.1140])
        self.heat_map = heat_map + 10
        self.map_height, self.map_width, _ = occ_map.shape
        self.best_distance = float('inf')
        self.best_node = None
        self.neural_bias = neural_bias

    def generate_random_sample(self):
        while True:
            x = random.randint(0, self.map_width - 1)
            y = random.randint(0, self.map_height - 1)
            if self.occ_map[y, x] != 0:
                return y, x

    def generate_neural_sample(self):
        # print("______________________________________________________________________________________________________")
        # Flatten the heatmap to a 1D array
        flat_heatmap = self.heat_map.flatten()
        # print(flat_heatmap)

        # Add a constant to shift the values to be non-negative
        # shifted_heatmap = flat_heatmap - np.min(flat_heatmap) + 1e-6
        shifted_heatmap = flat_heatmap - np.min(flat_heatmap)
        # print(shifted_heatmap)

        # Calculate the weights by taking the exponential of the shifted heatmap
        # weights = np.exp(shifted_heatmap)
        weights = shifted_heatmap
        # print(weights)

        # Normalize the weights to sum up to 1
        normalized_weights = weights / np.sum(weights)
        # print(normalized_weights)

        # Generate a random value between 0 and 1
        random_value = random.uniform(0, 1)
        # print(random_value)

        # Calculate the cumulative weights
        cumulative_weights = np.cumsum(normalized_weights)
        # print(cumulative_weights)

        # Find the index where the random value falls in the cumulative weights
        index = np.searchsorted(cumulative_weights, random_value)
        # print(index)

        # Convert the index back to 2D coordinates
        height, width, _ = self.heat_map.shape
        heat_map_shape = height, width
        y, x = np.unravel_index(index-1, heat_map_shape)
        # print("______________________________________________________________________________________________________")
        return y, x

    def find_nearest_neighbor(self, sample):
        nearest_node = None
        min_dist = float('inf')

        for node in self.nodes:
            dist = distance.euclidean(node.position, sample)
            if dist < min_dist:
                min_dist = dist
                nearest_node = node

        return nearest_node

    def steer(self, from_node, to_point):
        # vector to new node
        direction = (to_point[0] - from_node.position[0], to_point[1] - from_node.position[1])
        dist = math.sqrt(direction[0] ** 2 + direction[1] ** 2)

        # scaling down the vector if it exceeds max_step_size
        if dist > self.max_step_size:
            direction = (direction[0] * self.max_step_size / dist, direction[1] * self.max_step_size / dist)

        # recalculate the distance
        dist = math.sqrt(direction[0] ** 2 + direction[1] ** 2)
        new_cost = from_node.cost + dist  # Calculate the new cost

        new_node = Node((from_node.position[0] + direction[0], from_node.position[1] + direction[1]), new_cost)
        new_node.parent = from_node

        return new_node

    def connect_nodes(self, from_node, to_node):
        if self.is_collision_free(from_node.position, to_node.position):
            from_node.children.append(to_node)
            to_node.parent = from_node
            return True
        else:
            return False

    def is_collision_free(self, point1, point2):
        dist = np.linalg.norm(np.array(point1) - np.array(point2))
        to_check = np.linspace(0, dist, num=100)
        # print(point1)
        # print(point2)
        # print(to_check)
        if point1 == point2:
            return False

        for dis_int in to_check:
            y = int(point1[0] - ((dis_int * (point1[0] - point2[0])) / dist))
            x = int(point1[1] - ((dis_int * (point1[1] - point2[1])) / dist))
            # print(y, x)
            if self.occ_map[y, x] == 0:
                return False

        return True

    def rewire_tree(self, new_node):
        nearby_nodes = self.find_nearby_nodes(new_node, self.radius)

        for node in nearby_nodes:
            new_cost = new_node.cost + distance.euclidean(node.position, new_node.position)
            if new_cost < node.cost:
                if self.is_collision_free(node.position, new_node.position):
                    node.parent.children.remove(node)
                    node.parent = new_node
                    new_node.children.append(node)
                    node.cost = new_cost

    def find_nearby_nodes(self, node, radius):
        nearby_nodes = []
        for other_node in self.nodes:
            distance.euclidean(node.position, other_node.position)
            if distance.euclidean(node.position, other_node.position) <= radius:
                nearby_nodes.append(other_node)
        return nearby_nodes

    def goal_reached(self, node, goal):
        dist = distance.euclidean(node.position, goal)
        # print(dist)
        if dist < self.best_distance:
            self.best_distance = dist
            self.best_node = node
        return dist <= self.goal_threshold

    def find_path(self, goal):
        path = []
        current_node = goal

        while current_node is not None:
            path.append(current_node.position)
            current_node = current_node.parent

        path.reverse()  # Reverse the path to start from the start node
        return path

    def rrt_star(self):
        goal_node = None

        for _ in range(self.max_iterations):
            print("ITERATION:", _)
            print("BEST DISTANCE:", self.best_distance)

            if random.random() < self.neural_bias:
                random_sample = self.generate_neural_sample()
            else:
                random_sample = self.generate_random_sample()

            nearest_neighbor = self.find_nearest_neighbor(random_sample)
            # print("NEAREST_NEIGBOR", nearest_neighbor.position)
            # print("NEAREST_NEIGBOR", nearest_neighbor.cost)
            new_node = self.steer(nearest_neighbor, random_sample)
            # print("NEW_NODE", new_node.position)
            # print("NEW_NODE", new_node.cost)

            if self.connect_nodes(nearest_neighbor, new_node):
                self.rewire_tree(new_node)

                if self.goal_reached(new_node, self.goal):
                    goal_node = new_node
                    # Break for now, if tuned better it can iterate for longer to find better path?
                    break
                self.nodes.append(new_node)

        if goal_node is None:  # Goal not reached
            goal_node = self.best_node  # Take the closest node to goal TODO should be checked for obstacle
            # return None

        # Find the best path from the goal to the start
        path = self.find_path(goal_node)
        return path

    def visualize_tree(self, mask):
        fig, ax = plt.subplots(1, 3)
        ax[0].set_aspect('equal')

        # Plot obstacles or occupancy map if available
        if self.occ_map is not None:
            ax[0].imshow(self.occ_map, cmap='gray', origin='lower')

        # Plot nodes and connections
        for node in self.nodes:
            for child in node.children:
                y_values = [node.position[0], child.position[0]]
                x_values = [node.position[1], child.position[1]]
                ax[0].plot(x_values, y_values, 'b-')

        # Set start and goal markers if available
        if self.start_node.position is not None:
            ax[0].plot(self.start_node.position[1], self.start_node.position[0], 'go', markersize=8, label='Start')
        if self.goal is not None:
            ax[0].plot(self.goal[1], self.goal[0], 'ro', markersize=8, label='Goal')

        ax[0].legend()
        ax[1].imshow(self.heat_map)
        ax[1].invert_yaxis()
        ax[2].imshow(mask)
        ax[2].invert_yaxis()
        plt.xlabel('X')
        plt.ylabel('Y')
        plt.title('RRT* Tree Visualization')
        plt.show()

    def visualize_path(self, path, mask):
        fig, ax = plt.subplots(1, 3)
        ax[0].set_aspect('equal')

        # Plot obstacles or occupancy map if available
        if self.occ_map is not None:
            ax[0].imshow(self.occ_map, cmap='gray', origin='lower')

        # Plot path
        y_values = [position[0] for position in path]
        x_values = [position[1] for position in path]
        ax[0].plot(x_values, y_values, 'r-', linewidth=2, label='Path')

        # Plot nodes and connections
        for node in self.nodes:
            for child in node.children:
                y_values = [node.position[0], child.position[0]]
                x_values = [node.position[1], child.position[1]]
                ax[0].plot(x_values, y_values, 'b-', alpha=0.2)

        # Set start and goal markers if available
        if self.start_node.position is not None:
            ax[0].plot(self.start_node.position[1], self.start_node.position[0], 'go', markersize=8, label='Start')
        if self.goal is not None:
            ax[0].plot(self.goal[1], self.goal[0], 'ro', markersize=8, label='Goal')

        ax[0].legend()
        ax[1].imshow(self.heat_map)
        ax[1].invert_yaxis()
        ax[2].imshow(mask)
        ax[2].invert_yaxis()
        plt.xlabel('X')
        plt.ylabel('Y')
        plt.title('RRT* Path Visualization')
        plt.show()


def generate_paths():
    MAX_ITERATIONS = 5000
    MAX_STEP_SIZE = 20.0
    NEARBY_NODES_RADIUS = 10.0
    GOAL_THRESHOLD = 5.0

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
    image, mask, coords = batch

    occ_map = image.data.detach().cpu().numpy()
    occ_map = occ_map.transpose((0, 2, 3, 1))
    occ_map = occ_map[0]

    ideal_mask = mask.data.detach().cpu().numpy()
    ideal_mask = ideal_mask.transpose((0, 2, 3, 1))
    ideal_mask = ideal_mask[0]

    timer_neural_start = perf_counter()
    with torch.no_grad():
        output = model(image, coords)
    y_hat_np = output.detach().cpu().numpy()
    y_hat_np = y_hat_np.transpose((0, 2, 3, 1))
    clipped = np.clip(y_hat_np[0].copy(), -10, None)

    x_start = coords.data.tolist()[0][0][0][0]
    y_start = coords.data.tolist()[0][0][0][1]
    x_finish = coords.data.tolist()[0][0][1][0]
    y_finish = coords.data.tolist()[0][0][1][1]
    start = (y_start, x_start)
    finish = (y_finish, x_finish)

    rrt_neural = RRTStar(occ_map=occ_map, heat_map=clipped, start=start, goal=finish, max_iterations=MAX_ITERATIONS,
                  max_step_size=MAX_STEP_SIZE, nearby_nodes_radius=NEARBY_NODES_RADIUS, goal_threshold=GOAL_THRESHOLD,
                  neural_bias=0.5)
    path = rrt_neural.rrt_star()
    timer_neural_stop = perf_counter()

    if path:
        rrt_neural.visualize_tree(ideal_mask)
        rrt_neural.visualize_path(path, ideal_mask)
    else:
        print("COULDN'T FIND A PATH FOR THIS EXAMPLE:", start, finish)

    # print(f'Calculation time of neural RRT: {timer_neural_stop-timer_neural_start}')
    # -----------------------------------------------------------------------------------------------------------------
    timer_rrt_start = perf_counter()
    rrt = RRTStar(occ_map=occ_map, heat_map=clipped, start=start, goal=finish, max_iterations=MAX_ITERATIONS,
                  max_step_size=MAX_STEP_SIZE, nearby_nodes_radius=NEARBY_NODES_RADIUS, goal_threshold=GOAL_THRESHOLD,
                  neural_bias=-1.0)
    path = rrt.rrt_star()
    timer_rrt_stop = perf_counter()

    if path:
        rrt.visualize_tree(ideal_mask)
        rrt.visualize_path(path, ideal_mask)
    else:
        print("COULDN'T FIND A PATH FOR THIS EXAMPLE:", start, finish)

    print(f'Calculation time of neural RRT: {timer_neural_stop - timer_neural_start}')
    print(f'Calculation time of normal RRT: {timer_rrt_stop - timer_rrt_start}')


if __name__ == '__main__':
    generate_paths()