# Experiments

- `configs/`: one config per experiment (model, features, split, seed). Created with the first experiment.
- `results/`: run outputs. Git-ignored; summarized results are written to `reports/`.

Each experiment records its data version, split dates, features, hyperparameters, random seed and metrics so it can be reproduced. MLflow will track runs once there are models to compare.
