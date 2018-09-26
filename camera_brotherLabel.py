#!/bin/python

#Imports
import datetime
import os
from time import sleep
from PIL import Image
import random
import RPi.GPIO as GPIO
import picamera

#############
### Debug ###
#############
# These options allow you to run a quick test of the app.
# Both options must be set to 'False' when running as proper photobooth
TESTMODE_AUTOPRESS_BUTTON = False # Button will be pressed automatically, and app will exit after 1 photo cycle
TESTMODE_FAST             = False # Reduced wait between photos and 2 photos only

########################
### Variables Config ###
########################
pin_camera_btn = 26 # pin that the 'take photo' button is attached to
pin_exit_btn   = 13 # pin that the 'exit app' button is attached to (OPTIONAL BUTTON FOR EXITING THE APP)
pin_flash      = 16 # pin that is attached to the flash LED
total_pics = 4      # number of pics to be taken
prep_delay = 4      # number of seconds as users prepare to have photo taken
photo_w = 1920      # take photos at this resolution
photo_h = 1152
screen_w = 800      # resolution of the photo booth display
screen_h = 480

if TESTMODE_FAST:
    total_pics = 2     # number of pics to be taken
    prep_delay = 2     # number of seconds at step 1 as users prep to have photo taken

##############################
### Setup Objects and Pins ###
##############################
#Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_camera_btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_exit_btn  , GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_flash , GPIO.OUT)

#Setup Camera
camera = picamera.PiCamera()
#camera.rotation = 270
camera.annotate_text_size = 80
camera.resolution = (photo_w, photo_h)
camera.hflip = True # When preparing for photos, the preview will be flipped horizontally.

####################
### Other Config ###
####################
REAL_PATH = os.path.dirname(os.path.realpath(__file__))

########################
### Helper Functions ###
########################
def print_overlay(string_to_print):
    """
    Writes a string to both [i] the console, and [ii] camera.annotate_text
    """
    print(string_to_print)
    camera.annotate_text = string_to_print

def get_base_filename_for_images():
    """
    For each photo-capture cycle, a common base filename shall be used,
    based on the current timestamp.

    Example:
    ${ProjectRoot}/photos/2017-12-31_23-59-59

    The example above, will later result in:
    ${ProjectRoot}/photos/2017-12-31_23-59-59_1of4.png, being used as a filename.
    """
    base_filename = REAL_PATH + '/photos/' + str(datetime.datetime.now()).split('.')[0]
    base_filename = base_filename.replace(' ', '_')
    base_filename = base_filename.replace(':', '-')
    return base_filename

def flash():
    GPIO.output(pin_flash, 1)
    sleep(0.01)
    GPIO.output(pin_flash, 0)

def remove_overlay(overlay_id):
    """
    If there is an overlay, remove it
    """
    if overlay_id != -1:
        camera.remove_overlay(overlay_id)

# overlay one image on screen
def overlay_image(image_path, duration=0, layer=3):
    """
    Add an overlay (and sleep for an optional duration).
    If sleep duration is not supplied, then overlay will need to be removed later.
    This function returns an overlay id, which can be used to remove_overlay(id).
    """

    # "The camera`s block size is 32x16 so any image data
    #  provided to a renderer must have a width which is a
    #  multiple of 32, and a height which is a multiple of
    #  16."
    #  Refer: http://picamera.readthedocs.io/en/release-1.10/recipes1.html#overlaying-images-on-the-preview

    # Load the arbitrarily sized image
    img = Image.open(image_path)

    # Create an image padded to the required size with
    # mode 'RGB'
    pad = Image.new('RGB', (
        ((img.size[0] + 31) // 32) * 32,
        ((img.size[1] + 15) // 16) * 16,
    ))

    # Paste the original image into the padded one
    pad.paste(img, (0, 0))

    #Get the padded image data
    try:
        padded_img_data = pad.tobytes()
    except AttributeError:
        padded_img_data = pad.tostring() # Note: tostring() is deprecated in PIL v3.x

    # Add the overlay with the padded image as the source,
    # but the original image's dimensions
    o_id = camera.add_overlay(padded_img_data, size=img.size)
    o_id.layer = layer

    if duration > 0:
        sleep(duration)
        camera.remove_overlay(o_id)
        return -1 # '-1' indicates there is no overlay
    else:
        return o_id # we have an overlay, and will need to remove it later


###############
### Screens ###
###############

def prep_for_photo_screen(photo_number):
    """
    Prompt the user to get ready for the next photo
    """

    #Get ready for the next photo
    get_ready_image = REAL_PATH + "/assets/get_ready_"+str(photo_number)+".png"
    overlay_image(get_ready_image, prep_delay)

def taking_photo(photo_number, filename_prefix):
    """
    This function captures the photo
    """

    #get filename to use
    filename = filename_prefix + '_' + str(photo_number) + 'of'+ str(total_pics)+'.jpg'

    #countdown from 3, and display countdown on screen
    for counter in range(5,0,-1):
        print_overlay("             ..." + str(counter))
        sleep(1)

    #Take still
    camera.annotate_text = ''
    camera.capture(filename)
    flash()
    print("Photo (" + str(photo_number) + ") saved: " + filename)


def playback_screen(filename_prefix):
    """
    Final screen before main loop restarts
    """

    #Processing
    print("Displaying photos...")
    processing_image = REAL_PATH + "/assets/processing.png"
    overlay_image(processing_image, 2)
    
    #Playback
    prev_overlay = False
    for photo_number in range(1, total_pics + 1):
        filename = filename_prefix + '_' + str(photo_number) + 'of'+ str(total_pics)+'.jpg'
        this_overlay = overlay_image(filename, False, 3+total_pics)
        # The idea here, is only remove the previous overlay after a new overlay is added.
        if prev_overlay:
            remove_overlay(prev_overlay)
        sleep(2)
        prev_overlay = this_overlay
    remove_overlay(prev_overlay)

    #All done
    print("All done!")
    finished_image = REAL_PATH + "/assets/all_done_delayed_upload.png"
    overlay_image(finished_image, 5)

def combine_images(filename_prefix):
    print("Processing images into combined strip")

    processing_image = REAL_PATH + "/assets/processing.png"
    printing_overlay = overlay_image(processing_image)

    # Do the merging
    blankImage = Image.open(REAL_PATH + "/assets/blank.jpg")

    image1 = Image.open(filename_prefix + '_1of4.jpg')
    image1 = image1.resize((732,439))
    blankImage.paste(image1, (20,20))

    image2 = Image.open(filename_prefix + '_2of4.jpg')
    image2 = image2.resize((732,439))
    blankImage.paste(image2, (20,479))

    image3 = Image.open(filename_prefix + '_3of4.jpg')
    image3 = image3.resize((732,439))
    blankImage.paste(image3, (20,938))

    image4 = Image.open(filename_prefix + '_4of4.jpg')
    image4 = image4.resize((732,439))
    blankImage.paste(image4, (20,1397))

    blankImage.save(filename_prefix + '_combined.jpg', 'JPEG', quality=100)

    combinedImage = (filename_prefix + '_combined.jpg')

    print("Creating binary file for printer")
    os.system('brother_ql_create --dither --model QL-570 ' + combinedImage + ' > ' + combinedImage + '.bin')

    print("Sending file to printer")
    os.system('cat ' + combinedImage + '.bin > /dev/usb/lp0')

    print("Deleting binary file")
    os.system('rm -f ' + combinedImage + '.bin')

    remove_overlay(printing_overlay)

def main():
    """
    Main program loop
    """

    #Start Program
    print("Welcome to the photo booth!")
    print("Press the button to take a photo")

    #Start camera preview
    camera.start_preview(resolution=(screen_w, screen_h))

    #Display intro screen
    intro_image_1 = REAL_PATH + "/assets/intro_1.png"
    intro_image_2 = REAL_PATH + "/assets/intro_2.png"
    overlay_1 = overlay_image(intro_image_1, 0, 3)
    overlay_2 = overlay_image(intro_image_2, 0, 4)

    #Wait for someone to push the button
    i = 0
    blink_speed = 5
    while True:

        #Use falling edge detection to see if button is pushed
        is_pressed = GPIO.wait_for_edge(pin_camera_btn, GPIO.FALLING, timeout=100)
        exit_button = GPIO.wait_for_edge(pin_exit_btn, GPIO.FALLING, timeout=100)

        if exit_button is not None:
            return #Exit the photo booth

        if TESTMODE_AUTOPRESS_BUTTON:
            is_pressed = True

        #Stay inside loop, until button is pressed
        if is_pressed is None:

            #After every 5 cycles, alternate the overlay
            i = i+1
            if i==blink_speed:
                overlay_2.alpha = 255
            elif i==(2*blink_speed):
                overlay_2.alpha = 0
                i=0
#                if random.randint(1,101) > 80:
#		    flash()

            #Regardless, restart loop
            continue

        #Button has been pressed!
        filename_prefix = get_base_filename_for_images()
        print("Button pressed! You folks are in for a treat!")
        remove_overlay(overlay_2)
        remove_overlay(overlay_1)

        for photo_number in range(1, total_pics + 1):
            prep_for_photo_screen(photo_number)
            taking_photo(photo_number, filename_prefix)

        #combine images into photo strip
        combine_images(filename_prefix)

        #thanks for playing
        playback_screen(filename_prefix)

        # If we were doing a test run, exit here.
        if TESTMODE_AUTOPRESS_BUTTON:
            break

        # Otherwise, display intro screen again
        overlay_1 = overlay_image(intro_image_1, 0, 3)
        overlay_2 = overlay_image(intro_image_2, 0, 4)
        print("Press the button to take a photo")

if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("goodbye")

    except Exception as exception:
        print("unexpected error: ", str(exception))

    finally:
        camera.stop_preview()
        camera.close()
        GPIO.cleanup()
