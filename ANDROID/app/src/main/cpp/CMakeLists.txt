cmake_minimum_required(VERSION 3.22.1)

project("whisper")

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 16KB page alignment for Android 15+ compatibility
# This ensures native libraries work on devices with 16KB page sizes
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-z,max-page-size=16384")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,-z,max-page-size=16384")

# Add whisper.cpp as subdirectory
# You need to clone whisper.cpp here:
# git clone https://github.com/ggml-org/whisper.cpp.git whisper
add_subdirectory(whisper)

# JNI wrapper library
add_library(
    whisper-jni
    SHARED
    whisper-jni.cpp
)

# Link whisper and log libraries
target_link_libraries(
    whisper-jni
    whisper
    log
)

# Include whisper headers
target_include_directories(
    whisper-jni
    PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/whisper/include
    ${CMAKE_CURRENT_SOURCE_DIR}/whisper
)
