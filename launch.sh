eval "$(conda shell.bash hook)"
conda activate aants

SECONDS=0
PREV_ELAPSED=$SECONDS
ELAPSED=3600

# if failed in last hour do not restart
BURST_FAIL=3600

let "DIFFERENCE=ELAPSED-PREV_ELAPSED"

while (( DIFFERENCE >= BURST_FAIL )); do
	python dispatcher.py --run &> logs/dispatcher_python.log

	PREV_ELAPSED=$ELAPSED
	ELAPSED=$SECONDS
	let "DIFFERENCE=ELAPSED-PREV_ELAPSED"
	echo "$ELAPSED : $PREV_ELAPSED : $DIFFERENCE"
done



# if [ $? -ne 0 ]; then
python failure.py
# fi
