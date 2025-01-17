"""
=======================
Decoding real-time data
=======================

Supervised machine learning applied to MEG data in sensor space.
Here the classifier is updated every 5 trials and the decoding
accuracy is plotted
"""
# Authors: Mainak Jas <mainak@neuro.hut.fi>
#
# License: BSD (3-clause)

print(__doc__)

import time

import mne
from mne.realtime import MockRtClient, RtEpochs
from mne.datasets import sample

import numpy as np
import matplotlib.pyplot as plt

# Fiff file to simulate the realtime client
data_path = sample.data_path()
raw_fname = data_path + '/MEG/sample/sample_audvis_filt-0-40_raw.fif'
raw = mne.io.Raw(raw_fname, preload=True)

tmin, tmax = -0.2, 0.5
event_id = dict(aud_l=1, vis_l=3)

tr_percent = 60  # Training percentage
min_trials = 10  # minimum trials after which decoding should start

# select gradiometers
picks = mne.pick_types(raw.info, meg='grad', eeg=False, eog=True,
                       stim=True, exclude=raw.info['bads'])

# create the mock-client object
rt_client = MockRtClient(raw)

# create the real-time epochs object
rt_epochs = RtEpochs(rt_client, event_id, tmin, tmax, picks=picks, decim=1,
                     reject=dict(grad=4000e-13, eog=150e-6))

# start the acquisition
rt_epochs.start()

# send raw buffers
rt_client.send_data(rt_epochs, picks, tmin=0, tmax=90, buffer_size=1000)

# Decoding in sensor space using a linear SVM
n_times = len(rt_epochs.times)

from sklearn import preprocessing
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.cross_validation import cross_val_score, ShuffleSplit

from mne.decoding import ConcatenateChannels, FilterEstimator

scores_x, scores, std_scores = [], [], []

filt = FilterEstimator(rt_epochs.info, 1, 40)
scaler = preprocessing.StandardScaler()
concatenator = ConcatenateChannels()
clf = SVC(C=1, kernel='linear')

concat_classifier = Pipeline([('filter', filt), ('concat', concatenator),
                              ('scaler', scaler), ('svm', clf)])

for ev_num, ev in enumerate(rt_epochs.iter_evoked()):

    print("Just got epoch %d" % (ev_num + 1))

    if ev_num == 0:
        X = ev.data[None, ...]
        y = int(ev.comment)
    else:
        X = np.concatenate((X, ev.data[None, ...]), axis=0)
        y = np.append(y, int(ev.comment))

    if ev_num >= min_trials:

        cv = ShuffleSplit(len(y), 5, test_size=0.2, random_state=42)
        scores_t = cross_val_score(concat_classifier, X, y, cv=cv,
                                   n_jobs=1) * 100

        std_scores.append(scores_t.std())
        scores.append(scores_t.mean())
        scores_x.append(ev_num)

        # Plot accuracy
        plt.clf()

        plt.plot(scores_x[-5:], scores[-5:], '+', label="Classif. score")
        plt.hold(True)
        plt.plot(scores_x[-5:], scores[-5:])
        plt.axhline(50, color='k', linestyle='--', label="Chance level")
        hyp_limits = (np.asarray(scores[-5:]) - np.asarray(std_scores[-5:]),
                      np.asarray(scores[-5:]) + np.asarray(std_scores[-5:]))
        plt.fill_between(scores_x[-5:], hyp_limits[0], y2=hyp_limits[1],
                         color='b', alpha=0.5)
        plt.xlabel('Trials')
        plt.ylabel('Classification score (% correct)')
        plt.ylim([30, 105])
        plt.title('Real-time decoding')
        plt.show()

        time.sleep(0.1)
