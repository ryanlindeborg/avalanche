import unittest

import PIL
import torch
from PIL import ImageChops
from PIL.Image import Image
from torch import Tensor
from torch.utils.data import TensorDataset, random_split, Subset
from torchvision.datasets import MNIST
from torchvision.transforms import ToTensor, RandomCrop, ToPILImage, Compose, \
    Lambda, CenterCrop

from avalanche.benchmarks.utils import AvalancheDataset, \
    AvalancheSubset, AvalancheConcatDataset
from avalanche.benchmarks.utils.dataset_utils import ConstantSequence
from avalanche.training.utils import load_all_dataset
import random

from avalanche.benchmarks.scenarios.generic_scenario_creation import \
    create_generic_scenario_from_tensors

import numpy as np

from tests.unit_tests_utils import common_setups


def pil_images_equal(img_a, img_b):
    diff = ImageChops.difference(img_a, img_b)

    return not diff.getbbox()


class AvalancheDatasetTests(unittest.TestCase):
    def setUp(self):
        common_setups()

    def test_mnist_no_transforms(self):
        dataset = MNIST('./data/mnist', download=True)
        x, y = dataset[0]
        self.assertIsInstance(x, Image)
        self.assertEqual([x.width, x.height], [28, 28])
        self.assertIsInstance(y, int)

    def test_mnist_native_transforms(self):
        dataset = MNIST('./data/mnist', download=True, transform=ToTensor())
        x, y = dataset[0]
        self.assertIsInstance(x, Tensor)
        self.assertEqual(x.shape, (1, 28, 28))
        self.assertIsInstance(y, int)

    def test_avalanche_dataset_transform(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x, y = dataset_mnist[0]
        dataset = AvalancheDataset(dataset_mnist, transform=ToTensor())
        x2, y2, t2 = dataset[0]

        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(y2, int)
        self.assertIsInstance(t2, int)
        self.assertEqual(0, t2)
        self.assertTrue(torch.equal(ToTensor()(x), x2))
        self.assertEqual(y, y2)

    def test_avalanche_dataset_slice(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x0, y0 = dataset_mnist[0]
        x1, y1 = dataset_mnist[1]
        dataset = AvalancheDataset(dataset_mnist, transform=ToTensor())
        x2, y2, t2 = dataset[:2]
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(y2, Tensor)
        self.assertIsInstance(t2, Tensor)
        self.assertTrue(torch.equal(ToTensor()(x0), x2[0]))
        self.assertTrue(torch.equal(ToTensor()(x1), x2[1]))
        self.assertEqual(y0, y2[0].item())
        self.assertEqual(y1, y2[1].item())
        self.assertEqual(0, t2[0].item())
        self.assertEqual(0, t2[1].item())

    def test_avalanche_dataset_indexing(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x0, y0 = dataset_mnist[0]
        x1, y1 = dataset_mnist[5]
        dataset = AvalancheDataset(dataset_mnist, transform=ToTensor())
        x2, y2, t2 = dataset[0, 5]
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(y2, Tensor)
        self.assertIsInstance(t2, Tensor)
        self.assertTrue(torch.equal(ToTensor()(x0), x2[0]))
        self.assertTrue(torch.equal(ToTensor()(x1), x2[1]))
        self.assertEqual(y0, y2[0].item())
        self.assertEqual(y1, y2[1].item())
        self.assertEqual(0, t2[0].item())
        self.assertEqual(0, t2[1].item())

    def test_avalanche_dataset_composition(self):
        dataset_mnist = MNIST('./data/mnist', download=True,
                              transform=RandomCrop(16))
        x, y = dataset_mnist[0]
        self.assertIsInstance(x, Image)
        self.assertEqual([x.width, x.height], [16, 16])
        self.assertIsInstance(y, int)

        dataset = AvalancheDataset(
            dataset_mnist, transform=ToTensor(),
            target_transform=lambda target: -1)

        x2, y2, t2 = dataset[0]
        self.assertIsInstance(x2, Tensor)
        self.assertEqual(x2.shape, (1, 16, 16))
        self.assertIsInstance(y2, int)
        self.assertEqual(y2, -1)
        self.assertIsInstance(t2, int)
        self.assertEqual(0, t2)
        
    def test_avalanche_dataset_add(self):
        dataset_mnist = MNIST('./data/mnist', download=True,
                              transform=CenterCrop(16))

        dataset1 = AvalancheDataset(
            dataset_mnist, transform=ToTensor(),
            target_transform=lambda target: -1)

        dataset2 = AvalancheDataset(
            dataset_mnist, target_transform=lambda target: -2,
            task_labels=ConstantSequence(2, len(dataset_mnist)))
        
        dataset3 = dataset1 + dataset2
        
        self.assertEqual(len(dataset_mnist)*2, len(dataset3))

        x1, y1, t1 = dataset1[0]
        x2, y2, t2 = dataset2[0]

        x3, y3, t3 = dataset3[0]
        x3_2, y3_2, t3_2 = dataset3[len(dataset_mnist)]

        self.assertIsInstance(x1, Tensor)
        self.assertEqual(x1.shape, (1, 16, 16))
        self.assertEqual(-1, y1)
        self.assertEqual(0, t1)

        self.assertIsInstance(x2, PIL.Image.Image)
        self.assertEqual(x2.size, (16, 16))
        self.assertEqual(-2, y2)
        self.assertEqual(2, t2)

        self.assertEqual((y1, t1), (y3, t3))
        self.assertEqual(16 * 16, torch.sum(torch.eq(x1, x3)).item())

        self.assertEqual((y2, t2), (y3_2, t3_2))
        self.assertTrue(pil_images_equal(x2, x3_2))

    def test_avalanche_dataset_uniform_task_labels(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x, y = dataset_mnist[0]
        dataset = AvalancheDataset(dataset_mnist, transform=ToTensor(),
                                   task_labels=[1] * len(dataset_mnist))
        x2, y2, t2 = dataset[0]

        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(y2, int)
        self.assertIsInstance(t2, int)
        self.assertEqual(1, t2)
        self.assertTrue(torch.equal(ToTensor()(x), x2))
        self.assertEqual(y, y2)

        self.assertListEqual([1] * len(dataset_mnist),
                             list(dataset.targets_task_labels))

        subset_task1 = dataset.task_set[1]
        self.assertIsInstance(subset_task1, AvalancheDataset)
        self.assertEqual(len(dataset), len(subset_task1))

        with self.assertRaises(KeyError):
            subset_task0 = dataset.task_set[0]

    def test_avalanche_dataset_mixed_task_labels(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x, y = dataset_mnist[0]

        random_task_labels = [random.randint(0, 10)
                              for _ in range(len(dataset_mnist))]
        dataset = AvalancheDataset(dataset_mnist, transform=ToTensor(),
                                   task_labels=random_task_labels)
        x2, y2, t2 = dataset[0]

        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(y2, int)
        self.assertIsInstance(t2, int)
        self.assertEqual(random_task_labels[0], t2)
        self.assertTrue(torch.equal(ToTensor()(x), x2))
        self.assertEqual(y, y2)

        self.assertListEqual(random_task_labels,
                             list(dataset.targets_task_labels))

        u_labels, counts = np.unique(random_task_labels, return_counts=True)
        for i, task_label in enumerate(u_labels.tolist()):
            subset_task = dataset.task_set[task_label]
            self.assertIsInstance(subset_task, AvalancheDataset)
            self.assertEqual(int(counts[i]), len(subset_task))

            unique_task_labels = list(subset_task.targets_task_labels)
            self.assertListEqual([task_label] * int(counts[i]),
                                 unique_task_labels)

        with self.assertRaises(KeyError):
            subset_task11 = dataset.task_set[11]

    def test_avalanche_dataset_task_labels_inheritance(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        random_task_labels = [random.randint(0, 10)
                              for _ in range(len(dataset_mnist))]
        dataset_orig = AvalancheDataset(dataset_mnist, transform=ToTensor(),
                                        task_labels=random_task_labels)

        dataset_child = AvalancheDataset(dataset_orig)
        x2, y2, t2 = dataset_orig[0]
        x3, y3, t3 = dataset_child[0]

        self.assertIsInstance(t2, int)
        self.assertEqual(random_task_labels[0], t2)

        self.assertIsInstance(t3, int)
        self.assertEqual(random_task_labels[0], t3)

        self.assertListEqual(random_task_labels,
                             list(dataset_orig.targets_task_labels))

        self.assertListEqual(random_task_labels,
                             list(dataset_child.targets_task_labels))

    def test_avalanche_dataset_tensor_dataset_input(self):
        train_x = torch.rand(500, 3, 28, 28)
        train_y = torch.zeros(500)
        test_x = torch.rand(200, 3, 28, 28)
        test_y = torch.ones(200)

        train = TensorDataset(train_x, train_y)
        test = TensorDataset(test_x, test_y)
        train_dataset = AvalancheDataset(train)
        test_dataset = AvalancheDataset(test)

        self.assertEqual(500, len(train_dataset))
        self.assertEqual(200, len(test_dataset))

        x, y, t = train_dataset[0]
        self.assertIsInstance(x, Tensor)
        self.assertEqual(0, y)
        self.assertEqual(0, t)

        x2, y2, t2 = test_dataset[0]
        self.assertIsInstance(x2, Tensor)
        self.assertEqual(1, y2)
        self.assertEqual(0, t2)

    def test_avalanche_dataset_multiple_outputs_and_float_y(self):
        train_x = torch.rand(500, 3, 28, 28)
        train_y = torch.zeros(500)
        train_z = torch.ones(500)
        test_x = torch.rand(200, 3, 28, 28)
        test_y = torch.ones(200)
        test_z = torch.full((200,), 5)

        train = TensorDataset(train_x, train_y, train_z)
        test = TensorDataset(test_x, test_y, test_z)
        train_dataset = AvalancheDataset(train)
        test_dataset = AvalancheDataset(test)

        self.assertEqual(500, len(train_dataset))
        self.assertEqual(200, len(test_dataset))

        x, y, z, t = train_dataset[0]
        self.assertIsInstance(x, Tensor)
        self.assertEqual(0, y)
        self.assertEqual(1, z)
        self.assertEqual(0, t)

        x2, y2, z2, t2 = test_dataset[0]
        self.assertIsInstance(x2, Tensor)
        self.assertEqual(1, y2)
        self.assertEqual(5, z2)
        self.assertEqual(0, t2)

    def test_avalanche_dataset_from_pytorch_subset(self):
        tensor_x = torch.rand(500, 3, 28, 28)
        tensor_y = torch.randint(0, 100, (500,))

        whole_dataset = TensorDataset(tensor_x, tensor_y)

        train = Subset(whole_dataset, indices=list(range(400)))
        test = Subset(whole_dataset, indices=list(range(400, 500)))

        train_dataset = AvalancheDataset(train)
        test_dataset = AvalancheDataset(test)

        self.assertEqual(400, len(train_dataset))
        self.assertEqual(100, len(test_dataset))

        x, y, t = train_dataset[0]
        self.assertIsInstance(x, Tensor)
        self.assertTrue(torch.equal(tensor_x[0], x))
        self.assertTrue(torch.equal(tensor_y[0], y))
        self.assertEqual(0, t)

        self.assertTrue(torch.equal(torch.as_tensor(train_dataset.targets),
                                    tensor_y[:400]))

        x2, y2, t2 = test_dataset[0]
        self.assertIsInstance(x2, Tensor)
        self.assertTrue(torch.equal(tensor_x[400], x2))
        self.assertTrue(torch.equal(tensor_y[400], y2))
        self.assertEqual(0, t2)

        self.assertTrue(torch.equal(torch.as_tensor(test_dataset.targets),
                                    tensor_y[400:]))

    def test_avalanche_dataset_from_chained_pytorch_subsets(self):
        tensor_x = torch.rand(500, 3, 28, 28)
        tensor_y = torch.randint(0, 100, (500,))

        whole_dataset = TensorDataset(tensor_x, tensor_y)

        subset1 = Subset(whole_dataset, indices=list(range(400, 500)))
        subset2 = Subset(subset1, indices=[5, 7, 0])

        dataset = AvalancheDataset(subset2)

        self.assertEqual(3, len(dataset))

        x, y, t = dataset[0]
        self.assertIsInstance(x, Tensor)
        self.assertTrue(torch.equal(tensor_x[405], x))
        self.assertTrue(torch.equal(tensor_y[405], y))
        self.assertEqual(0, t)

        self.assertTrue(
            torch.equal(
                torch.as_tensor(dataset.targets),
                torch.as_tensor([tensor_y[405], tensor_y[407], tensor_y[400]])
            )
        )

    def test_avalanche_dataset_collate_fn(self):
        tensor_x = torch.rand(500, 3, 28, 28)
        tensor_y = torch.randint(0, 100, (500,))
        tensor_z = torch.randint(0, 100, (500,))

        def my_collate_fn(patterns):
            x_values = torch.stack([pat[0] for pat in patterns], 0)
            y_values = torch.tensor([pat[1] for pat in patterns]) + 1
            z_values = torch.tensor([-1 for _ in patterns])
            t_values = torch.tensor([pat[3] for pat in patterns])
            return x_values, y_values, z_values, t_values

        whole_dataset = TensorDataset(tensor_x, tensor_y, tensor_z)
        dataset = AvalancheDataset(whole_dataset, collate_fn=my_collate_fn)

        x, y, z, t = dataset[0]
        self.assertIsInstance(x, Tensor)
        self.assertTrue(torch.equal(tensor_x[0], x))
        self.assertTrue(torch.equal(tensor_y[0], y))
        self.assertEqual(0, t)

        x2, y2, z2, t2 = dataset[0:5]
        self.assertIsInstance(x, Tensor)
        self.assertTrue(torch.equal(tensor_x[0:5], x2))
        self.assertTrue(torch.equal(tensor_y[0:5]+1, y2))
        self.assertTrue(torch.equal(torch.full((5,), -1, dtype=torch.long), z2))
        self.assertTrue(torch.equal(torch.zeros(5, dtype=torch.long), t2))

        inherited = AvalancheDataset(dataset)

        x3, y3, z3, t3 = inherited[0:5]
        self.assertIsInstance(x, Tensor)
        self.assertTrue(torch.equal(tensor_x[0:5], x3))
        self.assertTrue(torch.equal(tensor_y[0:5] + 1, y3))
        self.assertTrue(torch.equal(torch.full((5,), -1, dtype=torch.long), z3))
        self.assertTrue(torch.equal(torch.zeros(5, dtype=torch.long), t3))


class TransformationSubsetTests(unittest.TestCase):
    def setUp(self):
        common_setups()

    def test_avalanche_subset_transform(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x, y = dataset_mnist[0]
        dataset = AvalancheSubset(dataset_mnist, transform=ToTensor())
        x2, y2, t2 = dataset[0]
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(y2, int)
        self.assertIsInstance(t2, int)
        self.assertTrue(torch.equal(ToTensor()(x), x2))
        self.assertEqual(y, y2)
        self.assertEqual(0, t2)

    def test_avalanche_subset_composition(self):
        dataset_mnist = MNIST('./data/mnist', download=True, transform=RandomCrop(16))
        x, y = dataset_mnist[0]
        self.assertIsInstance(x, Image)
        self.assertEqual([x.width, x.height], [16, 16])
        self.assertIsInstance(y, int)

        dataset = AvalancheSubset(
            dataset_mnist, transform=ToTensor(),
            target_transform=lambda target: -1)

        x2, y2, t2 = dataset[0]
        self.assertIsInstance(x2, Tensor)
        self.assertEqual(x2.shape, (1, 16, 16))
        self.assertIsInstance(y2, int)
        self.assertIsInstance(t2, int)
        self.assertEqual(y2, -1)
        self.assertEqual(0, t2)

    def test_avalanche_subset_indices(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x, y = dataset_mnist[1000]
        x2, y2 = dataset_mnist[1007]

        dataset = AvalancheSubset(
            dataset_mnist, indices=[1000, 1007])

        x3, y3, t3 = dataset[0]
        x4, y4, t4 = dataset[1]
        self.assertTrue(pil_images_equal(x, x3))
        self.assertEqual(y, y3)
        self.assertTrue(pil_images_equal(x2, x4))
        self.assertEqual(y2, y4)
        self.assertFalse(pil_images_equal(x, x4))
        self.assertFalse(pil_images_equal(x2, x3))

    def test_avalanche_subset_mapping(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        _, y = dataset_mnist[1000]

        mapping = list(range(10))
        other_classes = list(mapping)
        other_classes.remove(y)

        swap_y = random.choice(other_classes)

        mapping[y] = swap_y
        mapping[swap_y] = y

        dataset = AvalancheSubset(dataset_mnist, class_mapping=mapping)

        _, y2, _ = dataset[1000]
        self.assertEqual(y2, swap_y)

    def test_avalanche_subset_uniform_task_labels(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x, y = dataset_mnist[1000]
        x2, y2 = dataset_mnist[1007]

        # First, test by passing len(task_labels) == len(dataset_mnist)
        dataset = AvalancheSubset(
            dataset_mnist, indices=[1000, 1007],
            task_labels=[1] * len(dataset_mnist))

        x3, y3, t3 = dataset[0]
        x4, y4, t4 = dataset[1]
        self.assertEqual(y, y3)
        self.assertEqual(1, t3)
        self.assertEqual(y2, y4)
        self.assertEqual(1, t4)

        # Secondly, test by passing len(task_labels) == len(indices)
        dataset = AvalancheSubset(
            dataset_mnist, indices=[1000, 1007],
            task_labels=[1, 1])

        x3, y3, t3 = dataset[0]
        x4, y4, t4 = dataset[1]
        self.assertEqual(y, y3)
        self.assertEqual(1, t3)
        self.assertEqual(y2, y4)
        self.assertEqual(1, t4)

    def test_avalanche_subset_mixed_task_labels(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        x, y = dataset_mnist[1000]
        x2, y2 = dataset_mnist[1007]

        full_task_labels = [1] * len(dataset_mnist)
        full_task_labels[1000] = 2
        # First, test by passing len(task_labels) == len(dataset_mnist)
        dataset = AvalancheSubset(
            dataset_mnist, indices=[1000, 1007],
            task_labels=full_task_labels)

        x3, y3, t3 = dataset[0]
        x4, y4, t4 = dataset[1]
        self.assertEqual(y, y3)
        self.assertEqual(2, t3)
        self.assertEqual(y2, y4)
        self.assertEqual(1, t4)

        # Secondly, test by passing len(task_labels) == len(indices)
        dataset = AvalancheSubset(
            dataset_mnist, indices=[1000, 1007],
            task_labels=[3, 5])

        x3, y3, t3 = dataset[0]
        x4, y4, t4 = dataset[1]
        self.assertEqual(y, y3)
        self.assertEqual(3, t3)
        self.assertEqual(y2, y4)
        self.assertEqual(5, t4)

    def test_avalanche_subset_task_labels_inheritance(self):
        dataset_mnist = MNIST('./data/mnist', download=True)
        random_task_labels = [random.randint(0, 10)
                              for _ in range(len(dataset_mnist))]
        dataset_orig = AvalancheDataset(dataset_mnist, transform=ToTensor(),
                                        task_labels=random_task_labels)

        dataset_child = AvalancheSubset(dataset_orig,
                                        indices=[1000, 1007])
        _, _, t2 = dataset_orig[1000]
        _, _, t5 = dataset_orig[1007]
        _, _, t3 = dataset_child[0]
        _, _, t6 = dataset_child[1]

        self.assertEqual(random_task_labels[1000], t2)
        self.assertEqual(random_task_labels[1007], t5)
        self.assertEqual(random_task_labels[1000], t3)
        self.assertEqual(random_task_labels[1007], t6)

        self.assertListEqual(random_task_labels,
                             list(dataset_orig.targets_task_labels))

        self.assertListEqual([random_task_labels[1000],
                              random_task_labels[1007]],
                             list(dataset_child.targets_task_labels))


class TransformationTensorDatasetTests(unittest.TestCase):
    def setUp(self):
        common_setups()

    def test_tensor_dataset_helper_tensor_y(self):
        dataset_train_x = [torch.rand(50, 32, 32) for _ in range(5)]
        dataset_train_y = [torch.randint(0, 100, (50,)) for _ in range(5)]

        dataset_test_x = [torch.rand(23, 32, 32) for _ in range(5)]
        dataset_test_y = [torch.randint(0, 100, (23,)) for _ in range(5)]

        cl_scenario = create_generic_scenario_from_tensors(
            dataset_train_x, dataset_train_y, dataset_test_x, dataset_test_y,
            [0] * 5)

        self.assertEqual(5, len(cl_scenario.train_stream))
        self.assertEqual(5, len(cl_scenario.test_stream))
        self.assertEqual(5, cl_scenario.n_experiences)

        for exp_id in range(cl_scenario.n_experiences):
            scenario_train_x, scenario_train_y, _ = \
                load_all_dataset(cl_scenario.train_stream[exp_id].dataset)
            scenario_test_x, scenario_test_y, _ = \
                load_all_dataset(cl_scenario.test_stream[exp_id].dataset)

            self.assertTrue(torch.all(torch.eq(
                dataset_train_x[exp_id],
                scenario_train_x)))
            self.assertTrue(torch.all(torch.eq(
                dataset_train_y[exp_id],
                scenario_train_y)))
            self.assertSequenceEqual(
                dataset_train_y[exp_id].tolist(),
                cl_scenario.train_stream[exp_id].dataset.targets)
            self.assertEqual(0, cl_scenario.train_stream[exp_id].task_label)

            self.assertTrue(torch.all(torch.eq(
                dataset_test_x[exp_id],
                scenario_test_x)))
            self.assertTrue(torch.all(torch.eq(
                dataset_test_y[exp_id],
                scenario_test_y)))
            self.assertSequenceEqual(
                dataset_test_y[exp_id].tolist(),
                cl_scenario.test_stream[exp_id].dataset.targets)
            self.assertEqual(0, cl_scenario.test_stream[exp_id].task_label)

    def test_tensor_dataset_helper_list_y(self):
        dataset_train_x = [torch.rand(50, 32, 32) for _ in range(5)]
        dataset_train_y = [torch.randint(0, 100, (50,)).tolist()
                           for _ in range(5)]

        dataset_test_x = [torch.rand(23, 32, 32) for _ in range(5)]
        dataset_test_y = [torch.randint(0, 100, (23,)).tolist()
                          for _ in range(5)]

        cl_scenario = create_generic_scenario_from_tensors(
            dataset_train_x, dataset_train_y, dataset_test_x, dataset_test_y,
            [0] * 5)

        self.assertEqual(5, len(cl_scenario.train_stream))
        self.assertEqual(5, len(cl_scenario.test_stream))
        self.assertEqual(5, cl_scenario.n_experiences)

        for exp_id in range(cl_scenario.n_experiences):
            scenario_train_x, scenario_train_y, _ = \
                load_all_dataset(cl_scenario.train_stream[exp_id].dataset)
            scenario_test_x, scenario_test_y, _ = \
                load_all_dataset(cl_scenario.test_stream[exp_id].dataset)

            self.assertTrue(torch.all(torch.eq(
                dataset_train_x[exp_id],
                scenario_train_x)))
            self.assertSequenceEqual(
                dataset_train_y[exp_id],
                scenario_train_y.tolist())
            self.assertSequenceEqual(
                dataset_train_y[exp_id],
                cl_scenario.train_stream[exp_id].dataset.targets)
            self.assertEqual(0, cl_scenario.train_stream[exp_id].task_label)

            self.assertTrue(torch.all(torch.eq(
                dataset_test_x[exp_id],
                scenario_test_x)))
            self.assertSequenceEqual(
                dataset_test_y[exp_id],
                scenario_test_y.tolist())
            self.assertSequenceEqual(
                dataset_test_y[exp_id],
                cl_scenario.test_stream[exp_id].dataset.targets)
            self.assertEqual(0, cl_scenario.test_stream[exp_id].task_label)


class AvalancheDatasetTransformOpsTests(unittest.TestCase):
    def setUp(self):
        common_setups()

    def test_freeze_transforms(self):
        original_dataset = MNIST('./data/mnist', download=True)
        x, y = original_dataset[0]
        dataset = AvalancheDataset(original_dataset, transform=ToTensor())
        dataset_frozen = dataset.freeze_transforms()
        dataset_frozen.transform = None

        x2, y2, _ = dataset_frozen[0]
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(y2, int)
        self.assertTrue(torch.equal(ToTensor()(x), x2))
        self.assertEqual(y, y2)

        dataset.transform = None
        x2, y2, _ = dataset[0]
        self.assertIsInstance(x2, Image)

        x2, y2, _ = dataset_frozen[0]
        self.assertIsInstance(x2, Tensor)

    def test_freeze_transforms_chain(self):
        original_dataset = MNIST('./data/mnist', download=True,
                                 transform=ToTensor())
        x, *_ = original_dataset[0]
        self.assertIsInstance(x, Tensor)

        dataset_transform = AvalancheDataset(original_dataset,
                                             transform=ToPILImage())
        x, *_ = dataset_transform[0]
        self.assertIsInstance(x, Image)

        dataset_frozen = dataset_transform.freeze_transforms()

        x2, *_ = dataset_frozen[0]
        self.assertIsInstance(x2, Image)

        dataset_transform.transform = None

        x2, *_ = dataset_transform[0]
        self.assertIsInstance(x2, Tensor)

        dataset_frozen.transform = ToTensor()

        x2, *_ = dataset_frozen[0]
        self.assertIsInstance(x2, Tensor)

        dataset_frozen2 = dataset_frozen.freeze_transforms()

        x2, *_ = dataset_frozen2[0]
        self.assertIsInstance(x2, Tensor)

        dataset_frozen.transform = None

        x2, *_ = dataset_frozen2[0]
        self.assertIsInstance(x2, Tensor)
        x2, *_ = dataset_frozen[0]
        self.assertIsInstance(x2, Image)

    def test_add_transforms(self):
        original_dataset = MNIST('./data/mnist', download=True)
        x, _ = original_dataset[0]
        dataset = AvalancheDataset(original_dataset, transform=ToTensor())
        dataset_added = dataset.add_transforms(ToPILImage())
        x2, *_ = dataset[0]
        x3, *_ = dataset_added[0]
        self.assertIsInstance(x, Image)
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(x3, Image)

    def test_add_transforms_chain(self):
        original_dataset = MNIST('./data/mnist', download=True)
        x, _ = original_dataset[0]
        dataset = AvalancheDataset(original_dataset, transform=ToTensor())
        dataset_added = AvalancheDataset(dataset, transform=ToPILImage())
        x2, *_ = dataset[0]
        x3, *_ = dataset_added[0]
        self.assertIsInstance(x, Image)
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(x3, Image)

    def test_transforms_freeze_add_mix(self):
        original_dataset = MNIST('./data/mnist', download=True)
        x, _ = original_dataset[0]
        dataset = AvalancheDataset(original_dataset, transform=ToTensor())
        dataset_frozen = dataset.freeze_transforms()
        dataset_added = dataset_frozen.add_transforms(ToPILImage())

        self.assertEqual(None, dataset_frozen.transform)

        x2, *_ = dataset[0]
        x3, *_ = dataset_added[0]
        self.assertIsInstance(x, Image)
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(x3, Image)

        dataset_frozen = dataset_added.freeze_transforms()
        dataset_added.transform = None

        x4, *_ = dataset_frozen[0]
        x5, *_ = dataset_added[0]
        self.assertIsInstance(x4, Image)
        self.assertIsInstance(x5, Tensor)

    def test_replace_transforms(self):
        original_dataset = MNIST('./data/mnist', download=True)
        x, y = original_dataset[0]
        dataset = AvalancheDataset(original_dataset, transform=ToTensor())
        x2, *_ = dataset[0]
        dataset_reset = dataset.replace_transforms(None, None)
        x3, *_ = dataset_reset[0]

        self.assertIsInstance(x, Image)
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(x3, Image)

        dataset_reset.transform = ToTensor()

        x4, *_ = dataset_reset[0]
        self.assertIsInstance(x4, Tensor)

        dataset_reset.replace_transforms(None, None)

        x5, *_ = dataset_reset[0]
        self.assertIsInstance(x5, Tensor)

        dataset_other = AvalancheDataset(dataset_reset)
        dataset_other = dataset_other.replace_transforms(None, lambda l: l + 1)

        _, y6, _ = dataset_other[0]
        self.assertEqual(y+1, y6)

    def test_transforms_replace_freeze_mix(self):
        original_dataset = MNIST('./data/mnist', download=True)
        x, _ = original_dataset[0]
        dataset = AvalancheDataset(original_dataset, transform=ToTensor())
        x2, *_ = dataset[0]
        dataset_reset = dataset.replace_transforms(None, None)
        x3, *_ = dataset_reset[0]

        self.assertIsInstance(x, Image)
        self.assertIsInstance(x2, Tensor)
        self.assertIsInstance(x3, Image)

        dataset_frozen = dataset.freeze_transforms()

        x4, *_ = dataset_frozen[0]
        self.assertIsInstance(x4, Tensor)

        dataset_frozen_reset = dataset_frozen.replace_transforms(None, None)

        x5, *_ = dataset_frozen_reset[0]
        self.assertIsInstance(x5, Tensor)

    def test_transforms_groups_base_usage(self):
        original_dataset = MNIST('./data/mnist', download=True)
        dataset = AvalancheDataset(
            original_dataset,
            transform_groups=dict(train=(ToTensor(), None),
                                  eval=(None, Lambda(lambda t: float(t)))))

        x, y, _ = dataset[0]
        self.assertIsInstance(x, Tensor)
        self.assertIsInstance(y, int)

        dataset_test = dataset.eval()

        x2, y2, _ = dataset_test[0]
        x3, y3, _ = dataset[0]
        self.assertIsInstance(x2, Image)
        self.assertIsInstance(y2, float)
        self.assertIsInstance(x3, Tensor)
        self.assertIsInstance(y3, int)

        dataset_train = dataset.train()
        dataset.transform = None

        x4, y4, _ = dataset_train[0]
        x5, y5, _ = dataset[0]
        self.assertIsInstance(x4, Tensor)
        self.assertIsInstance(y4, int)
        self.assertIsInstance(x5, Image)
        self.assertIsInstance(y5, int)

    def test_transforms_groups_constructor_error(self):
        original_dataset = MNIST('./data/mnist', download=True)
        with self.assertRaises(Exception):
            # Test tuple has only one element
            dataset = AvalancheDataset(
                original_dataset,
                transform_groups=dict(train=(ToTensor(), None),
                                      eval=(Lambda(lambda t: float(t)))))

        with self.assertRaises(Exception):
            # Test is not a tuple has only one element
            dataset = AvalancheDataset(
                original_dataset,
                transform_groups=dict(train=(ToTensor(), None),
                                      eval=[None, Lambda(lambda t: float(t))]))

        with self.assertRaises(Exception):
            # Train is None
            dataset = AvalancheDataset(
                original_dataset,
                transform_groups=dict(train=None,
                                      eval=(None, Lambda(lambda t: float(t)))))

        with self.assertRaises(Exception):
            # transform_groups is not a dictionary
            dataset = AvalancheDataset(
                original_dataset,
                transform_groups='Hello world!')

    def test_transforms_groups_alternative_default_group(self):
        original_dataset = MNIST('./data/mnist', download=True)
        dataset = AvalancheDataset(
            original_dataset,
            transform_groups=dict(train=(ToTensor(), None), eval=(None, None)),
            initial_transform_group='eval')

        x, *_ = dataset[0]
        self.assertIsInstance(x, Image)

        dataset_test = dataset.eval()

        x2, *_ = dataset_test[0]
        x3, *_ = dataset[0]
        self.assertIsInstance(x2, Image)
        self.assertIsInstance(x3, Image)

    def test_transforms_groups_partial_constructor(self):
        original_dataset = MNIST('./data/mnist', download=True)
        dataset = AvalancheDataset(
            original_dataset, transform_groups=dict(train=(ToTensor(), None)))

        x, *_ = dataset[0]
        self.assertIsInstance(x, Tensor)

        dataset = dataset.eval()
        x2, *_ = dataset[0]
        self.assertIsInstance(x2, Tensor)

    def test_transforms_groups_multiple_groups(self):
        original_dataset = MNIST('./data/mnist', download=True)
        dataset = AvalancheDataset(
            original_dataset,
            transform_groups=dict(
                train=(ToTensor(), None),
                eval=(None, None),
                other=(Compose([ToTensor(),
                               Lambda(lambda tensor: tensor.numpy())]), None)))

        x, *_ = dataset[0]
        self.assertIsInstance(x, Tensor)

        dataset = dataset.eval()
        x2, *_ = dataset[0]
        self.assertIsInstance(x2, Image)

        dataset = dataset.with_transforms('other')
        x3, *_ = dataset[0]
        self.assertIsInstance(x3, np.ndarray)

    def test_transforms_add_group(self):
        original_dataset = MNIST('./data/mnist', download=True)
        dataset = AvalancheDataset(original_dataset)

        with self.assertRaises(Exception):
            # Can't add existing groups
            dataset = dataset.add_transforms_group('train', ToTensor(), None)

        with self.assertRaises(Exception):
            # Can't add group with bad names (must be str)
            dataset = dataset.add_transforms_group(123, ToTensor(), None)

        # Can't add group with bad names (must be str)
        dataset = dataset.add_transforms_group('other', ToTensor(), None)
        dataset_other = dataset.with_transforms('other')

        x, *_ = dataset[0]
        x2, *_ = dataset_other[0]
        self.assertIsInstance(x, Image)
        self.assertIsInstance(x2, Tensor)

        dataset_other2 = AvalancheDataset(dataset_other)

        # Checks that the train group is used on dataset_other2
        x3, *_ = dataset_other2[0]
        self.assertIsInstance(x3, Image)

        with self.assertRaises(Exception):
            # Can't add group if it already exists
            dataset_other2 = dataset_other2.add_transforms_group(
                'other', ToTensor(), None)

        dataset_other2 = dataset_other2.with_transforms('other')

        # Check that the above failed method didn't change the 'other' group
        x4, *_ = dataset_other2[0]
        self.assertIsInstance(x4, Tensor)

    def test_transformation_concat_dataset(self):
        original_dataset = MNIST('./data/mnist', download=True)
        original_dataset2 = MNIST('./data/mnist', download=True)

        dataset = AvalancheConcatDataset([original_dataset,
                                          original_dataset2])

        self.assertEqual(len(original_dataset) + len(original_dataset2),
                         len(dataset))

    def test_transformation_concat_dataset_groups(self):
        original_dataset = AvalancheDataset(
            MNIST('./data/mnist', download=True),
            transform_groups=dict(eval=(None, None), train=(ToTensor(), None)))
        original_dataset2 = AvalancheDataset(
            MNIST('./data/mnist', download=True),
            transform_groups=dict(train=(None, None), eval=(ToTensor(), None)))

        dataset = AvalancheConcatDataset([original_dataset,
                                          original_dataset2])

        self.assertEqual(len(original_dataset) + len(original_dataset2),
                         len(dataset))

        x, *_ = dataset[0]
        x2, *_ = dataset[len(original_dataset)]
        self.assertIsInstance(x, Tensor)
        self.assertIsInstance(x2, Image)

        dataset = dataset.eval()

        x3, *_ = dataset[0]
        x4, *_ = dataset[len(original_dataset)]
        self.assertIsInstance(x3, Image)
        self.assertIsInstance(x4, Tensor)


if __name__ == '__main__':
    unittest.main()
