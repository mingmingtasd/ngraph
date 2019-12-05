//*****************************************************************************
// Copyright 2017-2019 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//*****************************************************************************

#include "gtest/gtest.h"
#include "ngraph/ngraph.hpp"
#include "util/type_prop.hpp"

using namespace std;
using namespace ngraph;

TEST(type_prop, nms_incorrect_boxes_rank)
{
    try
    {
        const auto boxes = make_shared<op::Parameter>(element::f32, Shape{1, 2, 3, 4});
        const auto scores = make_shared<op::Parameter>(element::f32, Shape{1, 2, 3});

        make_shared<op::v1::NonMaxSuppression>(boxes, scores);
    }
    catch (const NodeValidationFailure& error)
    {
        EXPECT_HAS_SUBSTRING(error.what(), "Expected a 3D tensor for the 'boxes' input");
    }
}

TEST(type_prop, nms_incorrect_scores_rank)
{
    try
    {
        const auto boxes = make_shared<op::Parameter>(element::f32, Shape{1, 2, 3});
        const auto scores = make_shared<op::Parameter>(element::f32, Shape{1, 2});

        make_shared<op::v1::NonMaxSuppression>(boxes, scores);
    }
    catch (const NodeValidationFailure& error)
    {
        EXPECT_HAS_SUBSTRING(error.what(), "Expected a 3D tensor for the 'scores' input");
    }
}

TEST(type_prop, nms_incorrect_scheme_num_batches)
{
    try
    {
        const auto boxes = make_shared<op::Parameter>(element::f32, Shape{1, 2, 3});
        const auto scores = make_shared<op::Parameter>(element::f32, Shape{2, 2, 3});

        make_shared<op::v1::NonMaxSuppression>(boxes, scores);
    }
    catch (const NodeValidationFailure& error)
    {
        EXPECT_HAS_SUBSTRING(error.what(),
                             "The first dimension of both 'boxes' and 'scores' must match");
    }
}

TEST(type_prop, nms_incorrect_scheme_num_boxes)
{
    try
    {
        const auto boxes = make_shared<op::Parameter>(element::f32, Shape{1, 2, 3});
        const auto scores = make_shared<op::Parameter>(element::f32, Shape{1, 2, 3});

        make_shared<op::v1::NonMaxSuppression>(boxes, scores);
    }
    catch (const NodeValidationFailure& error)
    {
        EXPECT_HAS_SUBSTRING(error.what(),
                             "'boxes' and 'scores' input shapes must match at the second and third "
                             "dimension respectively");
    }
}

TEST(type_prop, nms_scalar_inputs_check)
{
    const auto boxes = make_shared<op::Parameter>(element::f32, Shape{1, 2, 4});
    const auto scores = make_shared<op::Parameter>(element::f32, Shape{1, 2, 2});

    const auto scalar = make_shared<op::Parameter>(element::f32, Shape{});
    const auto non_scalar = make_shared<op::Parameter>(element::f32, Shape{1});

    try
    {
        make_shared<op::v1::NonMaxSuppression>(boxes, scores, non_scalar, scalar, scalar);
    }
    catch (const NodeValidationFailure& error)
    {
        EXPECT_HAS_SUBSTRING(error.what(),
                             "Expected a scalar for the 'max_output_boxes_per_class' input");
    }

    try
    {
        make_shared<op::v1::NonMaxSuppression>(boxes, scores, scalar, non_scalar, scalar);
    }
    catch (const NodeValidationFailure& error)
    {
        EXPECT_HAS_SUBSTRING(error.what(), "Expected a scalar for the 'iou_threshold' input");
    }

    try
    {
        make_shared<op::v1::NonMaxSuppression>(boxes, scores, scalar, scalar, non_scalar);
    }
    catch (const NodeValidationFailure& error)
    {
        EXPECT_HAS_SUBSTRING(error.what(), "Expected a scalar for the 'score_threshold' input");
    }
}

TEST(type_prop, nms_out_shape)
{
    const auto boxes = make_shared<op::Parameter>(element::f32, Shape{1, 2, 4});
    const auto scores = make_shared<op::Parameter>(element::f32, Shape{1, 2, 2});

    const auto nms = make_shared<op::v1::NonMaxSuppression>(boxes, scores);
    const auto nms_out_ps = nms->output(0).get_partial_shape();

    EXPECT_TRUE(nms_out_ps.rank().is_static());
    EXPECT_EQ(static_cast<size_t>(nms_out_ps.rank()), 2);
    EXPECT_EQ(static_cast<size_t>(nms_out_ps[1]), 3);
}
