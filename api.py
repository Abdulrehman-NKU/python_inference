from flask import Flask, request, jsonify
import threading
import time
from flask_cors import CORS
from flask_socketio import SocketIO
import redis
import json

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

total_inference_it_can_handle = 2

inference_stopped_for_user_id = None
inference_stopped_for_model_id = None

inference_paused_for_user_id = None
inference_paused_for_model_id = None


thread_lock = threading.Lock()


redisClient = redis.Redis()


# Can be done with out hash_set, just add the stringified task in the queue


PENDING_TASK_QUEUE = "PENDING_TASK_QUEUE"
PENDING_TASK_DATA_HASH_MAP = "PENDING_TASK_DATA_HASH_MAP"


def emit_event_factory(user_id, model_id, total_infer_time):
    def emit_event(event, status, elapsed_time):
        socketio.emit(
            event,
            {
                "user_id": user_id,
                "model_id": model_id,
                "total_infer_time": total_infer_time,
                "elapsed_time": elapsed_time,
                "status": status,
            },
        )

    return emit_event


def long_running_task(model_id, total_infer_time, user_id, elapsed_time=0):

    global inference_stopped_for_user_id
    global inference_stopped_for_model_id

    global inference_paused_for_user_id
    global inference_paused_for_model_id

    global total_inference_it_can_handle

    emit_event = emit_event_factory(user_id, model_id, total_infer_time)

    with thread_lock:
        if total_inference_it_can_handle == 0:
            TASK_ID = f"{user_id}_{model_id}"
            redisClient.lpush(PENDING_TASK_QUEUE, TASK_ID)
            redisClient.hset(
                name=PENDING_TASK_DATA_HASH_MAP,
                key=TASK_ID,
                value=json.dumps(
                    {
                        "user_id": user_id,
                        "model_id": model_id,
                        "total_infer_time": total_infer_time,
                        "elapsed_time": elapsed_time,
                        "status": "Queued",
                    }
                ),
            )
            emit_event("queued", "Queued", elapsed_time)
            return  # QUEUED

    total_inference_it_can_handle -= 1

    emit_event("start", "Started", elapsed_time)

    infer_time = int(total_infer_time) - elapsed_time
    start_time = time.time()

    while (
        (time.time() - start_time) < infer_time
        and (compare_user_id_and_model_id_with_global(user_id, model_id) == False)
        and (
            compare_user_id_and_model_id_with_global(
                user_id, model_id, check_for_paused=True
            )
            == False
        )
    ):
        time.sleep(5)  # Sleep for 5 seconds

        new_elapsed_time = elapsed_time + int(time.time() - start_time)

        if compare_user_id_and_model_id_with_global(user_id, model_id):
            break

        elif compare_user_id_and_model_id_with_global(
            user_id, model_id, check_for_paused=True
        ):
            break

        else:
            emit_event("update", "In Progress", new_elapsed_time)

    # To avoid race conditions
    with thread_lock:
        total_inference_it_can_handle += 1

    if compare_user_id_and_model_id_with_global(user_id, model_id):
        inference_stopped_for_user_id = None
        inference_stopped_for_model_id = None
        emit_event("stop", "Stopped", 0)

    elif compare_user_id_and_model_id_with_global(
        user_id, model_id, check_for_paused=True
    ):

        inference_paused_for_model_id = None
        inference_paused_for_user_id = None
        emit_event("pause", "Paused", new_elapsed_time)

    else:
        emit_event("complete", "Completed", total_infer_time)

    with thread_lock:
        next_queued_task = redisClient.rpop(PENDING_TASK_QUEUE)
        if next_queued_task:
            next_queued_task_data = redisClient.hget(
                name=PENDING_TASK_DATA_HASH_MAP, key=next_queued_task
            )
            if next_queued_task_data:
                next_queued_task_data = json.loads(next_queued_task_data)
                thread = threading.Thread(
                    target=long_running_task,
                    args=(
                        next_queued_task_data["model_id"],
                        next_queued_task_data["total_infer_time"],
                        next_queued_task_data["user_id"],
                        next_queued_task_data["elapsed_time"],
                    ),
                )
                thread.start()
                redisClient.hdel(PENDING_TASK_DATA_HASH_MAP, next_queued_task)
            else:
                print("Error: No data found for the next queued task.")


@app.route("/stop", methods=["GET"])
def stop():
    global inference_stopped_for_user_id
    global inference_stopped_for_model_id

    data = request.args
    inference_stopped_for_model_id = data.get("model_id")
    inference_stopped_for_user_id = data.get("user_id")

    return (
        jsonify(
            {
                "message": f"Inference stopped for model_id {inference_stopped_for_model_id} and user_id {inference_stopped_for_user_id}",
            }
        ),
        200,
    )


@app.route("/pause", methods=["GET"])
def pause():
    global inference_paused_for_user_id
    global inference_paused_for_model_id

    data = request.args
    inference_paused_for_user_id = data.get("user_id")
    inference_paused_for_model_id = data.get("model_id")

    return (
        jsonify(
            {
                "message": f"Inference paused for model_id {inference_paused_for_model_id} and user_id {inference_paused_for_user_id}",
            }
        ),
        200,
    )


@app.route("/run", methods=["GET"])
def run():
    global inference_stopped_for_user_id
    global inference_stopped_for_model_id

    global inference_paused_for_user_id
    global inference_paused_for_model_id

    data = request.args
    user_id = data.get("user_id")
    model_id = data.get("model_id", "Unknown Model")
    infer_time = data.get("infer_time", 0)
    elapsed_time = int(data.get("elapsed_time", 0))
    attachment = data.get("attachment")

    print(f"Attachment to process alogngside is:{attachment}")

    if user_id is None:
        return (
            jsonify({"message": "Please provide a user_id"}),
            400,
        )

    if compare_user_id_and_model_id_with_global(user_id, model_id):
        inference_stopped_for_user_id = None
        inference_stopped_for_model_id = None

    if compare_user_id_and_model_id_with_global(user_id, model_id, True):
        inference_paused_for_model_id = None
        inference_paused_for_user_id = None

    # Start the long running task in a separate thread
    thread = threading.Thread(
        target=long_running_task, args=(model_id, infer_time, user_id, elapsed_time)
    )
    thread.start()

    return (
        jsonify(
            {
                "message": f"Inference requested for {model_id} for {infer_time} seconds",
                "status": "Requested",
            }
        ),
        202,
    )


def compare_user_id_and_model_id_with_global(user_id, model_id, check_for_paused=False):
    global inference_stopped_for_user_id
    global inference_stopped_for_model_id

    global inference_paused_for_user_id
    global inference_paused_for_model_id

    result = False
    if check_for_paused:
        with thread_lock:
            if (
                inference_paused_for_user_id == user_id
                and inference_paused_for_model_id == model_id
            ):
                result = True
    else:
        with thread_lock:
            if (
                inference_stopped_for_user_id == user_id
                and inference_stopped_for_model_id == model_id
            ):
                result = True

    return result


if __name__ == "__main__":
    app.run(debug=True, port=5001)
