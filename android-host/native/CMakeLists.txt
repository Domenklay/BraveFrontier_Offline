# Add this AFTER original upstream target "gimuserver" is defined.
cmake_minimum_required(VERSION 3.24)
if(NOT TARGET gimuserver)
    message(FATAL_ERROR "Must be included by the upstream server CMake project")
endif()
add_library(bf_offline_server SHARED NativeServer.cpp)
target_compile_features(bf_offline_server PRIVATE cxx_std_23)
target_include_directories(bf_offline_server PRIVATE "$"+"{CMAKE_SOURCE_DIR}")
# Include every original controller registration object (not merely referenced calls).
target_link_libraries(bf_offline_server PRIVATE
    "$"+"<LINK_LIBRARY:WHOLE_ARCHIVE,gimuserver>" log)
set_target_properties(bf_offline_server PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "$"+"{CMAKE_BINARY_DIR}/offline_native")
