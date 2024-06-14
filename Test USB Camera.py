import cv2  # Install opencv-python


# CAMERA can be 0 or 1 based on default camera of your computer
camera = cv2.VideoCapture(5)

while True:
    # Grab the webcamera's image.
    ret, image = camera.read()

    # Show the image in a window
    cv2.imshow("Webcam Image", image)

    # Listen to the keyboard for presses.
    keyboard_input = cv2.waitKey(1)

    # 27 is the ASCII for the esc key on your keyboard.
    if keyboard_input == 27:
        break

camera.release()
cv2.destroyAllWindows()
