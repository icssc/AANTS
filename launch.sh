eval "$(conda shell.bash hook)"
conda activate aants

python dispatcher.py --run &> logs/dispatcher_python.log

if [ $? -ne 0 ]; then
	python failure.py
fi
