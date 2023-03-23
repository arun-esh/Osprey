TRAIN = 1
TEST = 2
EVAL = 4

preconfiged_sessions = {
    "sample": {
        "commands": [
            ("train", {"epoch_num": 100, "batch_size": 64, "k_fold": 10}, "bow-v0"),
            ("test", {}, "test_bow")],

        "model_configs": {
            # Custom configs of a model as dict
        },
    },
    "ann": {
        "commands": [
            ("train", {"epoch_num": 110, "batch_size": 500, "k_fold": 10}, "bow-v0"),
            ("test", dict(), "bow-v0"),
            # ("eval", {"path": 'output/ann/'}, ""),
        ],
        "model_configs": {
            "dimension_list": list([32]),
            "activation": ("relu", dict()),
            "loss_func": ("BCEW", dict()),
            "lr": 0.01,
            "module_session_path": "output/ann/",
            "session_path_include_time": False,
            "number_of_classes": 1,
            "device": 'cuda'
        },
    },
}

preconfiged_datasets = {
    # "bow-v0": (
    #     "bow",  # short name of the dataset
    #     {       # train configs
    #         "data_path": "data/toy.train/toy-train.csv",
    #         "output_path": "data/preprocessed/ann/",
    #         "load_from_pkl": True,
    #         "preprocessings": ["sw", "pr", "rr"],
    #         "persist_data": True,
    #     },
    #     {      # test configs
    #         "data_path": "data/toy.test/toy-test.csv",
    #         "output_path": "data/preprocessed/ann/test-",
    #         "load_from_pkl": True,
    #         "preprocessings": ["sw", "pr", "rr"],
    #         "persist_data": True,
    #     }
    # ),

    # "bow-onehot": (
    #     "bow",  # short name of the dataset
    #     {  # train configs
    #         "data_path": "data/train/train.csv",
    #         "output_path": "data/preprocessed/ann/",
    #         "load_from_pkl": True,
    #         "preprocessings": ["sw", "pr", "rr"],
    #         "persist_data": True,
    #     },
    #     {  # test configs
    #         "data_path": "data/test/test.csv",
    #         "output_path": "data/preprocessed/ann/test-",
    #         "load_from_pkl": True,
    #         "preprocessings": ["sw", "pr", "rr"],
    #         "persist_data": True,
    #     }
    # ),
    #
    "balanced-bert-base-cased": (
        "tranformer/bert-base-cased",  # short name of the dataset
        {       # train configs
            "data_path": "data/balanced/train.csv",
            "output_path": "data/preprocessed/balanced-ann/",
            "load_from_pkl": True,
            "preprocessings": ["sw", "pr", "rr"],
            "persist_data": True,
        },
        {      # test configs
            "data_path": "data/balanced/test.csv",
            "output_path": "data/preprocessed/balanced-ann/test-",
            "load_from_pkl": True,
            "preprocessings": ["sw", "pr", "rr"],
            "persist_data": True,
        }
    ),
}

sessions = {
    # "ann-onehot": {
    #     "model": "ann",
    #     "commands": [
    #         # ("train", {"epoch_num": 10, "batch_size": 64, "k_fold": 10}, "bow-onehot"),
    #         # ("test", dict(), "bow-onehot"),
    #         ("eval", {"path": 'output/ann-onehot/ann/'}, ""),
    #     ],
    #     "model_configs": {
    #         "dimension_list": list([256, 128, 64]),
    #         "activation": ("relu", dict()),
    #         "loss_func": ("cross-entropy", {'reduction': 'mean'}),
    #         "lr": 0.001,
    #         "module_session_path": "output",
    #         "session_path_include_time": False,
    #         "number_of_classes": 2,
    #         "device": 'cuda'
    #     },
    # },

    # "ann-word2vec": {
    #     "commands": [
    #         ("train", {"epoch_num": 110, "batch_size": 500, "k_fold": 10}, "bow-v0"),
    #         ("test", dict(), "bow-v0"),
    #         ("eval", {"path": 'output/ann/'}, ""),
    #         ],
    #     "model_configs": {
    #         "dimension_list": list([32]),
    #         "activation": ("relu", dict()),
    #         "loss_func": ("BCEW", dict()),
    #         "lr": 0.01,
    #         "module_session_path": "output",
    #         "session_path_include_time": False,
    #         "number_of_classes": 1,
    #         "device": 'cuda'
    #     },
    # },

    "ann-bert": {
        "model": "ann",
        "commands": [
            ("train", {"epoch_num": 100, "batch_size": 128, "k_fold": 5}, "balanced-bert-base-cased"),
            ("test", dict(), "balanced-bert-base-cased"),
            # ("eval", {"path": 'output/ann-bert/ann/tranformer/bert-base-cased/'}, ""),
    ],
    "model_configs": {
        "dimension_list": list([64]),
        "activation": ("relu", dict()),
        "loss_func": ("cross-entropy", dict()),
        "lr": 0.01,
        "module_session_path": "output",
        "session_path_include_time": False,
        "number_of_classes": 2,
        "device": 'cuda'
    },
    },
}

datasets = preconfiged_datasets

FILTERED_CONFIGS = {
    "session_path_include_time",
    "data_path",
    "output_path",
    "load_from_pkl",
    "preprocessings",
    "persist_data",
}

IGNORED_PARAM_RESET = {"activation", "loss_function"}

USE_CUDA_IF_AVAILABLE = False
