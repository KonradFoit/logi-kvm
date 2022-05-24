# logi-kvm
Python script to synchronize Logitech Unifying devices channel switch and monitor input change

Provides switching Logitech Unifying devices channels and VCP compliant monitors input as a reaction to Logitech Easy Switch keys events

Notes:
    Unifying channels indexes starts at 0
    Unifying receiver slots indexes starts at 1
    Any Unifying Hardware should be compatible. In order to check what message has to be sent to the device to
    make it switch channel user has to check number of feature called "CHANGE HOST". This can be checked using
    software Solaar by listing devices via command 'solaar show'. This number has to be byte number 2 in
    switch_message in UnifyingDevice class. Byte number 3 in this message is, as for authors current knowledge,
    a magic byte and has to be found by try and error.
    Display number and input name has to be found by try and error.

    Default configuration is created in function populate_config
