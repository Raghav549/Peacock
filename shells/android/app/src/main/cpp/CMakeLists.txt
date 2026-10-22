cmake_minimum_required(VERSION 3.22.1)
project(peacock_shell C)

set(GENERATED "${CMAKE_CURRENT_SOURCE_DIR}/generated")
if(NOT EXISTS "${GENERATED}/program.c" OR NOT EXISTS "${GENERATED}/runtime.c")
    message(FATAL_ERROR "Run shells/android/prepare.sh before assembling the Android app")
endif()

add_library(peacock_program SHARED peacock_jni.c "${GENERATED}/program.c" "${GENERATED}/runtime.c")
target_include_directories(peacock_program PRIVATE "${GENERATED}")
target_compile_options(peacock_program PRIVATE -Wall -Wextra -Werror)
target_link_libraries(peacock_program m)
