CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -DNDEBUG
CPPFLAGS += -I../common

TARGET := astar_serial

.PHONY: all clean
all: $(TARGET)

$(TARGET): main.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ main.cpp

clean:
	rm -f $(TARGET)
