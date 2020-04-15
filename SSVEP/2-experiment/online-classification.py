import matplotlib.pyplot as plt

from mne.datasets import sample
from mne.io import  RawArray

from mne_realtime import LSLClient, MockLSLStream, RtEpochs, MockRtClient
import numpy as np
import pandas as pd
import mne as mne
from pylsl import StreamInlet, resolve_byprop, StreamInfo, StreamOutlet
import time
import threading
from pyriemann.classification import MDM, TSclassifier
from pyriemann.estimation import Covariances
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from joblib import  load
from scipy import stats

#defining the marker
info = StreamInfo('MarkerStream', 'Markers', 1, 0, 'int32', 'myuidw43536')
outlet = StreamOutlet(info)  #for sending the predicted classes

#defining the stream data format
sfreq = 250
ch_names = ['Unnamed: 1', 'Unnamed: 2', 'Unnamed: 3', "Unnamed: 4", "Unnamed: 5", "Unnamed: 6", "Unnamed: 7", "Unnamed: 8"]
ch_types = ['eeg'] * 8
info = mne.create_info(ch_names, sfreq, ch_types = ch_types)
host = 'OpenBCItestEEG'

######HYPERPARAMETERS
epoch_width = 2.6
waittime = 0.2
threshold = 0.5  #vs. probability printed by predict_proba
num_of_epochs = 5
#########

epoch_chunks = int(np.round(sfreq * epoch_width))  #freq * 2.6seconds

a = time.time()
arrayData = []  #for keeping the results

loaded_model = load("mdm.joblib")  #loading trained mod4
def runRT(count):
	with LSLClient(info=info, host=host, wait_max=3) as client:
		#print("data to array:",count, "  Start Time:",a-time.time())
		epoch = client.get_data_as_epoch(n_samples=epoch_chunks)
		#print("data to array:",count, "  End Time:",a-time.time())
		epoch.filter(9, 16, method='iir')
		X = epoch.get_data() * 1e-6 #n_epochs * n_channel * n_time_samples
		X=X[:,[0,1,2],:]	#get only the first three channels

		#print("data: ", X)
		res = loaded_model.predict(X)
		prob = loaded_model.predict_proba(X)
		#print("count: ",count," res: ",res, "prob: ", prob)
		#print("count: ",count," res: ",prob[0][res[0]-1])
		arrayData.append([res[0],prob[0][res[0]-1]])
		maxArray = len(arrayData)
		#print("Number of epochs:     ",maxArray)
		
		if (maxArray > num_of_epochs):  #make sure there is at least n number of epochs
			lastFive = np.array(arrayData[maxArray-num_of_epochs:maxArray][:]).transpose()  #tranpose the data
			#print("Last Five: ", lastFive)
			selectedRes  = stats.mode(lastFive[0])[0][0]   #get the most recurrent classes
			condition = np.equal(lastFive[0],selectedRes)   
			probRes = np.average(np.extract(condition, lastFive[1]))  #get the average probability of the most recurrent classes
			print("Result:  ",selectedRes)
			print("Probability: ", probRes)
			print("Threshold: ", threshold)
			print(probRes > threshold)

			if probRes > threshold:
				print("pushed")
				selectedRes = int(selectedRes)
				outlet.push_sample([selectedRes])

	    
count = 0
while(True):
	time.sleep(waittime)
	x= threading.Thread(target = runRT, args=(count,))
	x.start()
	count+=1
