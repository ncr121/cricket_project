# Independent Cricket Project

# Summary

Uses ball-by-ball data from cricsheet.org to obtain the frequency of outcomes (runs, wickets or extras). These frequencies are counted for different scenarios based on the inning, batter and bowler for example. New matches with artificial players can then be simulated where the outcome of each ball is determined by sampling from the stored data as different discrete distributions. Once the match has been run, various scorecards can be viewed.

# Data

The model was developed to simulate matches using ball-by-ball data from cricsheet.org, which has a database of matches since 2003. Currently only test match data is considered, but this model could be easily adapted for limited overs.

For simulating a match, there are different features for any given ball in the match that will change as the match progresses. For example: the position of the batter in the order, LH vs RH, pace vs spin, number of of overs in the inning, number of overs in the match, historical and match stats of the batter and bowler. 

If for example it is the the 15th over in an inning and a right arm fast bowler is bowling to the #4 batter. Then I will retrieve a discrete probability distribution (0, 1, 2, 3, 4, 6 or W) for each feature. In this example one feature is #4 batters, and its corresponding distribution was determined by counting the frequencies of #4 batter (0, 1, 2, 3, 4, 6 or W) for all balls faced by a #4 batter in the historical database. Other features for this ball, such as right arm fast and overs 11-20 have corresponding frequency vectors as well.

Once all feature vectors have been retrieved from historical frequencies, the probability distribution for that ball is computed using weights, which assign relative  importance to each feature. This final vector is then sampled from once to get an outcome for that ball. 

Currently the weights have been manually calibrated to ensure the overall predicted scores are close to actual match results. There are future plans to extend this frameowrk to optimise the weights by using RNNs.

In order to get these frequency vectors in the first place, for every ball in every match in the database a label was assigned for each feature (e.g. batter position, over in inning etc).
