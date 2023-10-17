import ctypes
import numpy as np
import pandas as pd
from tqdm import tqdm
from Models.utils import normalize
from Models.parallel_utils import run_parallel, CHUNK_SIZE
from utils import logger, textToOperator
from config import USGDict, topK, listLimit, outputsDir


# Parallel score calculators

def parallelScoreCalculatorUSG(userId, evalParamsId, modelParamsId, listLimit):
    # Extracting the list of parameters
    evalParams = ctypes.cast(evalParamsId, ctypes.py_object).value
    modelParams = ctypes.cast(modelParamsId, ctypes.py_object).value

    fusion, poiList, trainingMatrix = evalParams['fusion'], evalParams['poiList'], evalParams['trainingMatrix']
    alpha, beta = USGDict['alpha'], USGDict['beta']
    UScores, SScores, GScores = modelParams['U'], modelParams['S'], modelParams['G']

    UScoresNormal = normalize([UScores[userId, lid]
                               if trainingMatrix[userId, lid] == 0 else -1
                               for lid in poiList])
    SScoresNormal = normalize([SScores[userId, lid]
                               if trainingMatrix[userId, lid] == 0 else -1
                               for lid in poiList])
    GScoresNormal = normalize([GScores[userId, lid]
                               if trainingMatrix[userId, lid] == 0 else -1
                               for lid in poiList])
    UScoresNormal, SScoresNormal, GScoresNormal = np.array(
        UScoresNormal), np.array(SScoresNormal), np.array(GScoresNormal)

    overallScores = textToOperator(
        fusion, [(1.0 - alpha - beta) * UScoresNormal, alpha * SScoresNormal, beta * GScoresNormal])
    predicted = list(reversed(np.array(overallScores).argsort()))[:listLimit]
    return predicted


def parallelScoreCalculatorGeoSoCa(userId, evalParamsId, modelParamsId, listLimit):
    # Extracting the list of parameters
    evalParams = ctypes.cast(evalParamsId, ctypes.py_object).value
    modelParams = ctypes.cast(modelParamsId, ctypes.py_object).value

    fusion, poiList, trainingMatrix = evalParams['fusion'], evalParams['poiList'], evalParams['trainingMatrix']
    AKDEScores, SCScores, CCScores = modelParams['AKDE'], modelParams['SC'], modelParams['CC']

    # Check if Category is skipped
    overallScores = np.array([
        textToOperator(
            fusion,
            [AKDEScores[userId, lid], SCScores[userId, lid], CCScores[userId, lid]]
                if not (CCScores is None)
                else [AKDEScores[userId, lid], SCScores[userId, lid]]
        )
        if trainingMatrix[userId, lid] == 0 else -1
        for lid in poiList
    ])
    predicted = list(reversed(overallScores.argsort()))[:listLimit]
    return predicted


def parallelScoreCalculatorLORE(userId, evalParamsId, modelParamsId, listLimit):
    # Extracting the list of parameters
    evalParams = ctypes.cast(evalParamsId, ctypes.py_object).value
    modelParams = ctypes.cast(modelParamsId, ctypes.py_object).value

    fusion, poiList, trainingMatrix = evalParams['fusion'], evalParams['poiList'], evalParams['trainingMatrix']
    KDEScores, FCFScores, AMCScores = modelParams['KDE'], modelParams['FCF'], modelParams['AMC']

    overallScores = np.array([textToOperator(fusion, [KDEScores[userId, lid], FCFScores[userId, lid], AMCScores[userId, lid]])
                     if (userId, lid) not in trainingMatrix else -1
                     for lid in poiList])
    predicted = list(reversed(overallScores.argsort()))[:listLimit]
    return predicted


PARALLEL_FUNC_MAP = {
    'USG': parallelScoreCalculatorUSG,
    'GeoSoCa': parallelScoreCalculatorGeoSoCa,
    'LORE': parallelScoreCalculatorLORE,
}


def calculateScores(modelName: str, evalParams: dict, modelParams: dict,
                    listLimit: int):
    """
    Calculate the predictions dictionary (parallel computation).
    """

    usersList, groundTruth = evalParams['usersList'], evalParams['groundTruth']
    usersInGroundTruth = list((u for u in usersList if u in groundTruth))
    args = [(uid, id(evalParams), id(modelParams), listLimit) for uid in usersInGroundTruth]
    results = run_parallel(PARALLEL_FUNC_MAP[modelName], args, CHUNK_SIZE)
    predictions = {
        uid: preds
        for uid, preds in zip(usersInGroundTruth, results)
    }

    return predictions
